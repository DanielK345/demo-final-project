import pytest
from pydantic import ValidationError

from src.agents.history import (
    DeliveryEventMismatchError,
    DuplicateHistoryMessageError,
    InvalidDeliveryTransitionError,
    acknowledge_assistant_delivery,
    append_history_messages,
    build_message_id,
)
from src.agents.state import (
    AgentState,
    AssistantDeliveryEvent,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    ConversationSummary,
    DeliveryStatus,
)


def user_message(turn_id: str = "turn-001") -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.USER),
        turn_id=turn_id,
        role=ConversationRole.USER,
        message_type=ConversationMessageType.USER_TRANSCRIPT,
        content="Tôi muốn đặt xe",
        delivery_status=DeliveryStatus.FINAL,
        stt_confidence=0.98,
    )


def assistant_message(turn_id: str = "turn-001") -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.ASSISTANT),
        turn_id=turn_id,
        role=ConversationRole.ASSISTANT,
        message_type=ConversationMessageType.ASSISTANT_SPEECH,
        content="Bạn muốn đón ở đâu?",
        delivery_status=DeliveryStatus.PENDING,
    )


def test_agent_input_requires_turn_id():
    from src.agents.schemas import AgentInput

    with pytest.raises(ValidationError, match="turn_id"):
        AgentInput(session_id="session-001", transcript="Tôi muốn đặt xe")


def test_agent_input_normalizes_and_rejects_blank_turn_id():
    from src.agents.schemas import AgentInput

    agent_input = AgentInput(
        session_id="session-001",
        turn_id="  turn-001  ",
        transcript="Tôi muốn đặt xe",
    )
    assert agent_input.turn_id == "turn-001"

    with pytest.raises(ValidationError, match="turn_id cannot be blank"):
        AgentInput(
            session_id="session-001",
            turn_id="   ",
            transcript="Tôi muốn đặt xe",
        )


def test_message_ids_are_deterministic_and_validate_role():
    assert build_message_id("turn-001", ConversationRole.USER) == "turn-001:user"
    assert build_message_id("turn-001", ConversationRole.ASSISTANT) == "turn-001:assistant"
    assert build_message_id("turn-001", ConversationRole.TOOL, sequence=2) == "turn-001:tool-summary:2"

    with pytest.raises(ValidationError, match="does not match"):
        ConversationMessage(
            message_id="wrong-id",
            turn_id="turn-001",
            role=ConversationRole.USER,
            message_type=ConversationMessageType.USER_TRANSCRIPT,
            content="Xin chào",
            delivery_status=DeliveryStatus.FINAL,
        )


@pytest.mark.parametrize(
    ("role", "message_type", "status"),
    [
        (
            ConversationRole.USER,
            ConversationMessageType.ASSISTANT_SPEECH,
            DeliveryStatus.FINAL,
        ),
        (
            ConversationRole.USER,
            ConversationMessageType.USER_TRANSCRIPT,
            DeliveryStatus.PENDING,
        ),
        (
            ConversationRole.ASSISTANT,
            ConversationMessageType.ASSISTANT_SPEECH,
            DeliveryStatus.FINAL,
        ),
    ],
)
def test_message_rejects_invalid_role_type_or_status(role, message_type, status):
    with pytest.raises(ValidationError):
        ConversationMessage(
            message_id="turn-001:user",
            turn_id="turn-001",
            role=role,
            message_type=message_type,
            content="Nội dung",
            delivery_status=status,
        )


def test_pending_and_failed_speech_reject_spoken_content():
    for status in (DeliveryStatus.PENDING, DeliveryStatus.FAILED):
        with pytest.raises(ValidationError, match="spoken content"):
            ConversationMessage(
                message_id="turn-001:assistant",
                turn_id="turn-001",
                role=ConversationRole.ASSISTANT,
                message_type=ConversationMessageType.ASSISTANT_SPEECH,
                content="Bạn muốn đón ở đâu?",
                delivery_status=status,
                spoken_content="Bạn muốn",
            )


def test_history_rejects_duplicate_message_and_user_turn():
    first = user_message()
    with pytest.raises(DuplicateHistoryMessageError):
        append_history_messages([first], [first], max_messages=20)

    duplicate_turn = first.model_copy(update={"message_id": "another-id"})
    with pytest.raises(DuplicateHistoryMessageError, match="user transcript"):
        append_history_messages([first], [duplicate_turn], max_messages=20)


def test_state_rejects_duplicate_history_ids():
    message = user_message()
    with pytest.raises(ValidationError, match="duplicate message_id"):
        AgentState(
            session_id="session-001",
            conversation_history=[message, message],
        )


def test_delivery_acknowledgement_marks_full_message_delivered():
    message = assistant_message()
    updated = acknowledge_assistant_delivery(
        [user_message(), message],
        AssistantDeliveryEvent(
            session_id="session-001",
            turn_id="turn-001",
            message_id=message.message_id,
            status=DeliveryStatus.DELIVERED,
        ),
        session_id="session-001",
    )

    delivered = updated[-1]
    assert delivered.delivery_status is DeliveryStatus.DELIVERED
    assert delivered.spoken_content == delivered.content


def test_delivery_acknowledgement_preserves_interrupted_spoken_content():
    message = assistant_message()
    updated = acknowledge_assistant_delivery(
        [user_message(), message],
        AssistantDeliveryEvent(
            session_id="session-001",
            turn_id="turn-001",
            message_id=message.message_id,
            status=DeliveryStatus.INTERRUPTED,
            spoken_content="Bạn muốn",
        ),
        session_id="session-001",
    )

    assert updated[-1].delivery_status is DeliveryStatus.INTERRUPTED
    assert updated[-1].spoken_content == "Bạn muốn"


def test_delivered_acknowledgement_rejects_partial_spoken_content():
    message = assistant_message()
    with pytest.raises(DeliveryEventMismatchError, match="must match"):
        acknowledge_assistant_delivery(
            [user_message(), message],
            AssistantDeliveryEvent(
                session_id="session-001",
                turn_id="turn-001",
                message_id=message.message_id,
                status=DeliveryStatus.DELIVERED,
                spoken_content="Bạn muốn",
            ),
            session_id="session-001",
        )


def test_delivery_acknowledgement_rejects_mismatch_and_replay():
    message = assistant_message()
    event = AssistantDeliveryEvent(
        session_id="session-002",
        turn_id="turn-001",
        message_id=message.message_id,
        status=DeliveryStatus.DELIVERED,
    )
    with pytest.raises(DeliveryEventMismatchError, match="another session"):
        acknowledge_assistant_delivery(
            [message],
            event,
            session_id="session-001",
        )

    delivered = acknowledge_assistant_delivery(
        [message],
        event.model_copy(update={"session_id": "session-001"}),
        session_id="session-001",
    )
    with pytest.raises(InvalidDeliveryTransitionError):
        acknowledge_assistant_delivery(
            delivered,
            event.model_copy(update={"session_id": "session-001"}),
            session_id="session-001",
        )


def test_delivery_event_requires_terminal_status():
    with pytest.raises(ValidationError, match="terminal"):
        AssistantDeliveryEvent(
            session_id="session-001",
            turn_id="turn-001",
            message_id="turn-001:assistant",
            status=DeliveryStatus.PENDING,
        )


def test_conversation_summary_requires_unique_sources():
    with pytest.raises(ValidationError, match="duplicate source"):
        ConversationSummary(
            content="Khách đang đặt xe.",
            summarized_through_turn_id="turn-002",
            source_message_ids=["turn-001:user", "turn-001:user"],
        )
