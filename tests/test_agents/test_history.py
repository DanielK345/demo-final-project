import pytest
from pydantic import ValidationError

from src.agents.history import (
    DeliveryEventMismatchError,
    DuplicateHistoryMessageError,
    HistorySessionMismatchError,
    InvalidDeliveryTransitionError,
    acknowledge_assistant_delivery,
    append_history_messages,
    build_message_id,
    record_turn_history,
)
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
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


def test_delivery_acknowledgement_marks_failed_speech_without_spoken_content():
    message = assistant_message()
    updated = acknowledge_assistant_delivery(
        [user_message(), message],
        AssistantDeliveryEvent(
            session_id="session-001",
            turn_id="turn-001",
            message_id=message.message_id,
            status=DeliveryStatus.FAILED,
        ),
        session_id="session-001",
    )

    assert updated[-1].delivery_status is DeliveryStatus.FAILED
    assert updated[-1].spoken_content is None


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


def test_record_turn_adds_user_then_pending_assistant_atomically():
    state = AgentState(session_id="session-001")
    action = record_turn_history(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi muốn đặt xe",
            stt_confidence=0.97,
        ),
        state,
        AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn đón ở đâu?",
            state_updates={"retry_count": 1},
            reason="Internal reason must not be stored.",
        ),
    )

    history = action.state_updates["conversation_history"]
    assert [message.message_type for message in history] == [
        ConversationMessageType.USER_TRANSCRIPT,
        ConversationMessageType.ASSISTANT_SPEECH,
    ]
    assert history[0].stt_confidence == 0.97
    assert history[1].delivery_status is DeliveryStatus.PENDING
    assert "Internal reason" not in str(history)

    updated = state.apply(action.state_updates)
    assert updated.retry_count == 1
    assert updated.state_version == 1
    assert state.state_version == 0


def test_record_turn_masks_phone_without_changing_business_updates():
    action = record_turn_history(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Số của tôi là 0901234567",
        ),
        AgentState(session_id="session-001"),
        AgentAction(
            action_type=ActionType.RESPOND,
            message="Tôi đã nhận số 0901234567.",
            state_updates={
                "collected_data": {"phone_number": "0901234567"},
            },
        ),
    )

    history = action.state_updates["conversation_history"]
    assert all("0901234567" not in message.content for message in history)
    assert all("[REDACTED_PHONE]" in message.content for message in history)
    assert action.state_updates["collected_data"]["phone_number"] == "0901234567"


def test_call_tool_records_user_but_not_assistant_speech():
    action = record_turn_history(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Hồ Gươm",
        ),
        AgentState(session_id="session-001"),
        AgentAction(
            action_type=ActionType.CALL_TOOL,
            message="This message is not spoken while dispatching the tool.",
            tool_call={
                "tool_name": ToolName.SEARCH_PLACE,
                "call_id": "call-001",
                "params": {"query": "Hồ Gươm"},
            },
        ),
    )

    history = action.state_updates["conversation_history"]
    assert len(history) == 1
    assert history[0].message_type is ConversationMessageType.USER_TRANSCRIPT


def test_tool_only_turn_records_safe_summary_without_raw_payload():
    raw_secret = "provider-secret-payload"
    action = record_turn_history(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="call-001",
                status=ToolStatus.SUCCESS,
                data={"secret": raw_secret},
            ),
        ),
        AgentState(session_id="session-001"),
        AgentAction(
            action_type=ActionType.RESPOND,
            message="Đã tìm thấy địa điểm.",
            reason=raw_secret,
        ),
    )

    history = action.state_updates["conversation_history"]
    assert [message.message_type for message in history] == [
        ConversationMessageType.TOOL_SUMMARY,
        ConversationMessageType.ASSISTANT_SPEECH,
    ]
    assert raw_secret not in str(history)
    assert not any(message.message_type is ConversationMessageType.USER_TRANSCRIPT for message in history)


def test_record_turn_rejects_duplicate_turn_after_persisted_state():
    agent_input = AgentInput(
        session_id="session-001",
        turn_id="turn-001",
        transcript="Tôi muốn đặt xe",
    )
    original = AgentState(session_id="session-001")
    first_action = record_turn_history(
        agent_input,
        original,
        AgentAction(action_type=ActionType.ASK_USER, message="Bạn muốn đón ở đâu?"),
    )
    persisted = original.apply(first_action.state_updates)

    with pytest.raises(DuplicateHistoryMessageError):
        record_turn_history(
            agent_input,
            persisted,
            AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn muốn đón ở đâu?",
            ),
        )


def test_history_pruning_keeps_complete_recent_turns():
    history: list[ConversationMessage] = []
    for index in range(12):
        turn_id = f"turn-{index:03d}"
        history = append_history_messages(
            history,
            [user_message(turn_id), assistant_message(turn_id)],
            max_messages=AgentState.max_history_messages,
        )

    assert len(history) == AgentState.max_history_messages
    assert history[0].turn_id == "turn-002"
    assert history[0].message_type is ConversationMessageType.USER_TRANSCRIPT
    assert history[-1].turn_id == "turn-011"


def test_record_turn_rejects_state_from_another_session():
    with pytest.raises(HistorySessionMismatchError, match="same session"):
        record_turn_history(
            AgentInput(
                session_id="session-001",
                turn_id="turn-001",
                transcript="Tôi muốn đặt xe",
            ),
            AgentState(session_id="session-002"),
            AgentAction(action_type=ActionType.RESPOND, message="Xin chào"),
        )


def test_record_turn_bounds_long_transcript_without_rejecting_valid_input():
    action = record_turn_history(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="a" * 3000,
        ),
        AgentState(session_id="session-001"),
        AgentAction(action_type=ActionType.RESPOND, message="Đã tiếp nhận."),
    )

    user = action.state_updates["conversation_history"][0]
    assert len(user.content) == 2000
    assert user.content.endswith("...")
