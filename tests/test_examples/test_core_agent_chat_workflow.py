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
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> feature/agentic-ai
    assert session.state.current_step == BookingStep.COLLECT_VEHICLE

    fare = await session.user_turn("Cho tôi ô tô 4 chỗ")
    assert fare[-1].action_type is ActionType.ASK_USER
<<<<<<< HEAD
=======
>>>>>>> 86cfe2ef3e6996c4053492e822e3a2435384bcc3
>>>>>>> feature/agentic-ai
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

<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> feature/agentic-ai
    tracking = await session.user_turn("Xe của tôi còn bao lâu nữa tới?")
    assert tracking[-1].action_type is ActionType.RESPOND
    assert "4 phút" in (tracking[-1].message or "")

    cancel_confirmation = await session.user_turn("Hủy chuyến")
    assert cancel_confirmation[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.CONFIRM_CANCEL

    cancelled = await session.user_turn("Đúng")
    assert cancelled[-1].action_type is ActionType.RESPOND
    assert "hủy thành công" in (cancelled[-1].message or "")
    booking = BookingData.model_validate(session.state.collected_data["booking"])
    assert booking.booking_status == "CANCELLED"

<<<<<<< HEAD
=======
>>>>>>> 86cfe2ef3e6996c4053492e822e3a2435384bcc3
>>>>>>> feature/agentic-ai
    raw_user_messages = [
        message.content
        for message in session.state.conversation_history
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT
    ]
    assert "Không, đổi điểm đến sang Royal City" in raw_user_messages
    assert "Ừ đúng rồi, đặt giúp tôi đi" in raw_user_messages
<<<<<<< HEAD
    assert "Hủy chuyến" in raw_user_messages
=======
<<<<<<< HEAD
=======
    assert "Hủy chuyến" in raw_user_messages
>>>>>>> 86cfe2ef3e6996c4053492e822e3a2435384bcc3
>>>>>>> feature/agentic-ai


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
<<<<<<< HEAD
=======
<<<<<<< HEAD
=======
>>>>>>> feature/agentic-ai


@pytest.mark.asyncio
async def test_chat_recommends_vehicle_from_passengers_and_rejects_invalid_phone():
    session = offline_session("passenger-chat")

    route = await session.user_turn("Đặt xe từ VinUni đến Times City")
    assert route[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.COLLECT_VEHICLE

    selected = await session.user_turn(
        "Tôi đi 3 người, chọn phương tiện phù hợp"
    )
    assert selected[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.SELECT_VEHICLE_OPTION

    selected = await session.user_turn("Ô tô 4 chỗ")
    assert selected[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == BookingStep.COLLECT_PHONE
    booking = BookingData.model_validate(session.state.collected_data["booking"])
    assert booking.passenger_count == 3
    assert booking.vehicle_type == "CAR_4"

    invalid_phone = await session.user_turn("0123456789")
    assert invalid_phone[-1].action_type is ActionType.ASK_USER
    assert "hợp lệ" in (invalid_phone[-1].message or "")
    assert session.state.current_step == BookingStep.COLLECT_PHONE

    confirmation = await session.user_turn("0901234567")
    assert confirmation[-1].action_type is ActionType.ASK_USER
    assert "3 hành khách" in (confirmation[-1].message or "")
    assert "ô tô 4 chỗ" in (confirmation[-1].message or "").casefold()


@pytest.mark.asyncio
async def test_chat_selects_one_of_multiple_trips_without_speaking_booking_ids():
    session = offline_session("multi-trip-chat")

    started = await session.user_turn("Tra cứu chuyến của tôi")
    assert started[-1].action_type is ActionType.ASK_USER

    choices = await session.user_turn("0901234567")
    assert choices[-1].action_type is ActionType.ASK_USER
    assert session.state.current_step == "SELECT_TRIP"
    assert "DEMO-BOOKING" not in (choices[-1].message or "")

    selected = await session.user_turn("Chuyến số 1")
    assert selected[-1].action_type is ActionType.RESPOND
    assert "4 phút" in (selected[-1].message or "")
<<<<<<< HEAD
=======
>>>>>>> 86cfe2ef3e6996c4053492e822e3a2435384bcc3
>>>>>>> feature/agentic-ai
