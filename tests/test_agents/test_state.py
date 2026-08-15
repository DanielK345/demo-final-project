import pytest
from pydantic import ValidationError

from src.agents.contracts.schemas import ToolName, WorkflowType
from src.agents.contracts.state import (
    AgentState,
    ConfirmationStatus,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)


def test_state_updates_are_validated():
    state = AgentState(session_id="session-001")

    with pytest.raises(ValidationError):
        state.apply({"retry_count": -1})


def test_state_apply_returns_new_version_without_mutating_original():
    state = AgentState(session_id="session-001")

    updated = state.apply(
        {
            "current_workflow": WorkflowType.RIDE_BOOKING,
            "current_step": "COLLECT_PICKUP",
            "confirmation": ConfirmationStatus.AWAITING_CONFIRMATION,
        }
    )

    assert state.current_workflow is None
    assert state.state_version == 0
    assert updated.current_workflow is WorkflowType.RIDE_BOOKING
    assert updated.state_version == 1


def test_state_rejects_protected_field_updates():
    state = AgentState(session_id="session-001")

    with pytest.raises(ValueError, match="protected fields"):
        state.apply({"session_id": "session-002"})

    with pytest.raises(ValueError, match="protected fields"):
        state.apply({"state_version": 10})


def test_state_rejects_unknown_fields_and_update_typos():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentState(session_id="session-001", current_workfow="RIDE_BOOKING")

    with pytest.raises(ValueError, match="unknown fields: current_workfow"):
        AgentState(session_id="session-001").apply({"current_workfow": "RIDE_BOOKING"})


def test_current_step_requires_active_workflow():
    with pytest.raises(ValidationError, match="active workflow"):
        AgentState(session_id="session-001", current_step="COLLECT_PICKUP")


@pytest.mark.parametrize(
    "fields",
    [
        {"pending_tool_call_id": "call-001"},
        {"pending_tool_name": ToolName.SEARCH_PLACE},
    ],
)
def test_pending_tool_id_and_name_must_be_set_together(fields):
    with pytest.raises(ValidationError, match="must be set together"):
        AgentState(session_id="session-001", **fields)


def test_state_accepts_complete_pending_tool_identity():
    state = AgentState(
        session_id="session-001",
        pending_tool_call_id="call-001",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    assert state.pending_tool_call_id == "call-001"
    assert state.pending_tool_name is ToolName.SEARCH_PLACE


def test_append_message_keeps_bounded_history():
    state = AgentState(session_id="session-001")

    for index in range(AgentState.max_history_messages + 2):
        state = state.append_message(
            ConversationMessage(
                message_id=f"turn-{index}:user",
                turn_id=f"turn-{index}",
                role=ConversationRole.USER,
                message_type=ConversationMessageType.USER_TRANSCRIPT,
                content=f"message-{index}",
                delivery_status=DeliveryStatus.FINAL,
            )
        )

    assert len(state.conversation_history) == AgentState.max_history_messages
    assert state.conversation_history[0].content == "message-2"
    assert state.state_version == AgentState.max_history_messages + 2


def test_state_validates_stt_confidence():
    with pytest.raises(ValidationError):
        AgentState(session_id="session-001", last_stt_confidence=1.1)


def test_state_rejects_blank_session_and_pending_call_identifiers():
    with pytest.raises(ValidationError, match="session_id cannot be blank"):
        AgentState(session_id="   ")

    with pytest.raises(ValidationError, match="pending_tool_call_id cannot be blank"):
        AgentState(
            session_id="session-001",
            pending_tool_call_id="   ",
            pending_tool_name=ToolName.SEARCH_PLACE,
        )
