import pytest

from src.agents.contracts.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolCall,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.contracts.state import AgentState
from src.agents.core.guardrails import (
    AgentGuardrails,
    GuardrailViolationError,
    redact_pii,
    redact_pii_data,
)
from src.agents.core.policy import AgentPolicy


def test_guardrail_rejects_invalid_state_updates():
    with pytest.raises(GuardrailViolationError, match="invalid state"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(session_id="session-001", turn_id="turn-001", transcript="hello"),
            AgentState(session_id="session-001"),
            AgentAction(
                action_type=ActionType.ASK_USER,
                message="Hello",
                state_updates={"retry_count": -1},
            ),
        )


def test_guardrail_records_latest_stt_confidence_in_state_updates():
    action = AgentGuardrails().validate_and_sanitize(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Xin chào", stt_confidence=0.95),
        AgentState(session_id="session-001"),
        AgentAction(action_type=ActionType.RESPOND, message="Chào bạn!"),
    )

    assert action.state_updates["last_stt_confidence"] == 0.95


def test_redact_pii_masks_phone_numbers():
    assert redact_pii("Customer phone is 090 123 4567") == ("Customer phone is [REDACTED_PHONE]")


def test_guardrail_rejects_clearing_unresolved_side_effect_without_result():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_BOOKING_RESULT",
        pending_tool_call_id="booking-1",
        pending_tool_name=ToolName.CREATE_BOOKING,
        confirmation="CONFIRMED",
    )

    with pytest.raises(GuardrailViolationError, match="unresolved side effect"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-002",
                transcript="Tạm biệt",
            ),
            state,
            AgentAction(
                action_type=ActionType.END_SESSION,
                message="Tạm biệt.",
                state_updates={
                    "current_workflow": None,
                    "current_step": None,
                    "pending_tool_call_id": None,
                    "pending_tool_name": None,
                },
            ),
        )


def test_guardrail_rejects_clearing_side_effect_for_mismatched_tool_result():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_BOOKING_RESULT",
        pending_tool_call_id="booking-1",
        pending_tool_name=ToolName.CREATE_BOOKING,
        confirmation="CONFIRMED",
    )
    mismatched = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="search-1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    with pytest.raises(GuardrailViolationError, match="unresolved side effect"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-002",
                tool_result=mismatched,
            ),
            state,
            AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển tổng đài viên.",
                state_updates={
                    "current_workflow": WorkflowType.HUMAN_HANDOFF,
                    "current_step": "HANDOFF_REQUESTED",
                    "pending_tool_call_id": None,
                    "pending_tool_name": None,
                },
            ),
        )


def test_redact_pii_masks_labeled_booking_ids_and_nested_business_slots():
    assert redact_pii("booking ID: GSM-12345") == ("booking ID: [REDACTED_BOOKING_ID]")
    assert redact_pii_data(
        {
            "booking": {
                "phone_number": "0901234567",
                "booking_id": "GSM-12345",
                "status": "CONFIRMED",
            }
        }
    ) == {
        "booking": {
            "phone_number": "[REDACTED_PHONE]",
            "booking_id": "[REDACTED_BOOKING_ID]",
            "status": "CONFIRMED",
        }
    }


def test_guardrail_sets_tool_deadline_and_increments_session_budget():
    state = AgentState(session_id="session-001")
    call = ToolCall(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="search-1",
        params={"query": "VinUniversity"},
    )

    action = AgentGuardrails().validate_and_sanitize(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-001",
            transcript="VinUniversity",
        ),
        state,
        AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=call,
            state_updates={
                "current_workflow": WorkflowType.RIDE_BOOKING,
                "current_step": "WAITING_FOR_PICKUP_RESULT",
                "pending_tool_call_id": call.call_id,
                "pending_tool_name": call.tool_name,
            },
        ),
    )

    assert action.tool_call is not None
    assert action.tool_call.timeout_seconds == 5.0
    assert action.state_updates["tool_call_count"] == 1


def test_guardrail_blocks_tool_outside_workflow_and_exhausted_budget():
    call = ToolCall(
        tool_name=ToolName.LOOKUP_TRIP,
        call_id="lookup-1",
        params={"booking_id": "GSM-12345"},
    )
    action = AgentAction(
        action_type=ActionType.CALL_TOOL,
        tool_call=call,
        state_updates={
            "current_workflow": WorkflowType.FAQ,
            "current_step": "WAITING_FOR_KNOWLEDGE",
            "pending_tool_call_id": call.call_id,
            "pending_tool_name": call.tool_name,
        },
    )
    agent_input = AgentInput(
        session_id="session-001",
        turn_id="turn-001",
        transcript="tra cứu",
    )

    with pytest.raises(GuardrailViolationError, match="not allowed"):
        AgentGuardrails().validate_and_sanitize(
            agent_input,
            AgentState(session_id="session-001"),
            action,
        )

    booking_call = call.model_copy(update={"tool_name": ToolName.SEARCH_PLACE}, deep=True)
    booking_action = action.model_copy(
        update={
            "tool_call": booking_call,
            "state_updates": {
                **action.state_updates,
                "current_workflow": WorkflowType.RIDE_BOOKING,
                "pending_tool_name": ToolName.SEARCH_PLACE,
            },
        },
        deep=True,
    )
    with pytest.raises(GuardrailViolationError, match="tool-call limit"):
        AgentGuardrails(AgentPolicy(max_tool_calls_per_session=1)).validate_and_sanitize(
            agent_input,
            AgentState(session_id="session-001", tool_call_count=1),
            booking_action,
        )


def test_guardrail_rejects_invalid_or_unexpected_tool_params():
    state = AgentState(session_id="session-001")
    agent_input = AgentInput(
        session_id=state.session_id,
        turn_id="turn-001",
        transcript="tra cứu",
    )

    for params in ({}, {"booking_id": "GSM-12345", "admin": True}):
        call = ToolCall(
            tool_name=ToolName.LOOKUP_TRIP,
            call_id="lookup-1",
            params=params,
        )
        action = AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=call,
            state_updates={
                "current_workflow": WorkflowType.TRIP_LOOKUP,
                "current_step": "WAITING_FOR_TRIP_RESULT",
                "pending_tool_call_id": call.call_id,
                "pending_tool_name": call.tool_name,
            },
        )

        with pytest.raises(GuardrailViolationError, match="tool call"):
            AgentGuardrails().validate_and_sanitize(agent_input, state, action)


def test_guardrail_rejects_reconciliation_without_pending_side_effect():
    with pytest.raises(GuardrailViolationError, match="pending side effect"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-001",
                transcript="Hủy",
            ),
            AgentState(session_id="session-001"),
            AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển tổng đài viên.",
                state_updates={
                    "current_workflow": WorkflowType.HUMAN_HANDOFF,
                    "current_step": "RECONCILIATION_REQUIRED",
                },
            ),
        )


def test_guardrail_rejects_booking_without_provider_backed_resolved_location():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM",
        collected_data={
            "booking": {
                "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
                "destination": {"place_id": "", "display_name": "nhà"},
                "phone_number": "0901234567",
            }
        },
        confirmation="AWAITING_CONFIRMATION",
    )
    call = ToolCall(
        tool_name=ToolName.CREATE_BOOKING,
        call_id="booking-1",
        params={
            "pickup_place_id": "p1",
            "destination_place_id": "p2",
            "phone_number": "0901234567",
        },
    )

    with pytest.raises(GuardrailViolationError, match="concrete locations"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-002",
                transcript="Đúng, đặt giúp tôi",
            ),
            state,
            AgentAction(
                action_type=ActionType.CALL_TOOL,
                tool_call=call,
                state_updates={
                    "current_workflow": WorkflowType.RIDE_BOOKING,
                    "current_step": "WAITING_FOR_BOOKING_RESULT",
                    "pending_tool_call_id": "booking-1",
                    "pending_tool_name": ToolName.CREATE_BOOKING,
                    "confirmation": "CONFIRMED",
                },
            ),
        )


def test_guardrail_rejects_booking_params_that_differ_from_confirmed_state():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM",
        collected_data={
            "booking": {
                "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
                "destination": {"place_id": "d1", "display_name": "Times City"},
                "phone_number": "0901234567",
                "vehicle_type": "CAR_4",
                "fare_estimate_id": "fare-001",
            }
        },
        confirmation="AWAITING_CONFIRMATION",
    )
    call = ToolCall(
        tool_name=ToolName.CREATE_BOOKING,
        call_id="booking-1",
        params={
            "pickup_place_id": "p1",
            "destination_place_id": "d1",
            "phone_number": "0999999999",
            "vehicle_type": "CAR_4",
            "fare_estimate_id": "fare-001",
            "idempotency_key": "create-key",
        },
    )

    with pytest.raises(GuardrailViolationError, match="must match"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-002",
                transcript="Đúng",
            ),
            state,
            AgentAction(
                action_type=ActionType.CALL_TOOL,
                tool_call=call,
                state_updates={
                    "current_step": "WAITING_FOR_BOOKING_RESULT",
                    "pending_tool_call_id": call.call_id,
                    "pending_tool_name": call.tool_name,
                    "confirmation": "CONFIRMED",
                },
            ),
        )


def test_guardrail_rejects_cancel_booking_without_confirmation():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM_CANCEL",
        collected_data={"booking": {"booking_id": "booking-001", "booking_status": "CONFIRMED"}},
        confirmation="AWAITING_CONFIRMATION",
    )
    call = ToolCall(
        tool_name=ToolName.CANCEL_BOOKING,
        call_id="cancel-1",
        params={"booking_id": "booking-001", "idempotency_key": "cancel-key"},
    )

    with pytest.raises(GuardrailViolationError, match="explicit confirmed"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(
                session_id="session-001",
                turn_id="turn-002",
                transcript="Đúng",
            ),
            state,
            AgentAction(
                action_type=ActionType.CALL_TOOL,
                tool_call=call,
                state_updates={
                    "current_step": "WAITING_FOR_CANCELLATION_RESULT",
                    "pending_tool_call_id": call.call_id,
                    "pending_tool_name": call.tool_name,
                },
            ),
        )
