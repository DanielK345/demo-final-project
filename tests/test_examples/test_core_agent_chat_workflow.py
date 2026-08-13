import pytest

from examples.core_agent_chat import InteractiveSession
from src.agents.agent import LLMAgent
from src.agents.graph import AgentGraphAdapter
from src.agents.schemas import ActionType
from src.agents.state import ConversationMessageType
from src.agents.understanding.rewrite_service import PassthroughContextualRewriter
from src.agents.understanding.rules import RuleBasedUnderstanding
from src.agents.workflows.booking_models import BookingData, BookingStep


def offline_session(session_id: str) -> InteractiveSession:
    return InteractiveSession(
        session_id,
        graph=AgentGraphAdapter(
            LLMAgent(
                understanding_service=RuleBasedUnderstanding(),
                message_rewriter=PassthroughContextualRewriter(),
            )
        ),
    )


@pytest.mark.asyncio
async def test_full_conversation_repair_workflow_with_history_and_mock_backend():
    session = offline_session("full-p4-session")

    started = await session.user_turn(
        "Ờ, tôi muốn đặt xe từ VinUni đến Times City, bạn làm giúp nhé"
    )
    assert started[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.COLLECT_PHONE

    faq = await session.user_turn(
        "À mà trước khi đặt, dịch vụ có thanh toán tiền mặt không?"
    )
    assert faq[-1].action_type is ActionType.RESPOND
    assert "tiếp tục việc đặt xe" in (faq[-1].message or "").casefold()
    assert session.state.interrupted_workflow is not None

    resumed = await session.user_turn("Rồi, tiếp tục việc lúc nãy đi")
    assert resumed[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.COLLECT_PHONE
    assert session.state.interrupted_workflow is None

    confirmation = await session.user_turn("Số liên hệ là 090 123 4567 nhé")
    assert confirmation[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.CONFIRM

    repeated = await session.user_turn("Ơ bạn vừa nói gì, nhắc lại giúp tôi")
    assert repeated[-1].message == confirmation[-1].message
    assert session.state.current_step == BookingStep.CONFIRM

    corrected = await session.user_turn("Không, đổi điểm đến sang Royal City")
    assert corrected[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.CONFIRM
    booking = BookingData.model_validate(session.state.collected_data["booking"])
    assert booking.pickup is not None
    assert booking.pickup.display_name == "VinUniversity"
    assert booking.destination is not None
    assert booking.destination.display_name == "Royal City"
    assert booking.phone_number == "0901234567"

    completed = await session.user_turn("Ừ đúng rồi, đặt giúp tôi đi")
    assert completed[-1].action_type is ActionType.RESPOND
    assert "đặt thành công" in (completed[-1].message or "")
    booking = BookingData.model_validate(session.state.collected_data["booking"])
    assert booking.booking_id == "DEMO-BOOKING-001"

    raw_user_messages = [
        message.content
        for message in session.state.conversation_history
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT
    ]
    assert "Không, đổi điểm đến sang Royal City" in raw_user_messages
    assert "Ừ đúng rồi, đặt giúp tôi đi" in raw_user_messages


@pytest.mark.asyncio
async def test_two_interactive_sessions_do_not_share_memory_or_business_state():
    first = offline_session("memory-a")
    second = offline_session("memory-b")

    await first.user_turn("Tôi muốn đặt xe")

    assert first.state.conversation_history
    assert first.state.current_workflow == "RIDE_BOOKING"
    assert second.state.conversation_history == []
    assert second.state.current_workflow is None
    assert second.state.collected_data == {}
