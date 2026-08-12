import pytest

from src.agents.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.workflows.trip_lookup import TripLookupWorkflow
from src.agents.workflows.trip_lookup_models import TripLookupData, TripLookupStep


def apply_action(state: AgentState, action) -> AgentState:
    return state.apply(action.state_updates)


@pytest.mark.asyncio
async def test_trip_lookup_asks_for_identifier_when_missing():
    action = await TripLookupWorkflow().handle(
        AgentInput(session_id="session-001", transcript="Tra cứu chuyến của tôi"),
        AgentState(session_id="session-001"),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == TripLookupStep.COLLECT_IDENTIFIER
    assert action.tool_call is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transcript", "expected_params"),
    [
        ("Mã chuyến là GSM-12345", {"booking_id": "GSM-12345"}),
        ("090 123 4567", {"phone_number": "0901234567"}),
    ],
)
async def test_trip_lookup_calls_tool_with_valid_identifier(
    transcript: str,
    expected_params: dict,
):
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
    )

    action = await TripLookupWorkflow().handle(
        AgentInput(session_id="session-001", transcript=transcript),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.LOOKUP_TRIP
    assert action.tool_call.params == expected_params
    assert action.state_updates["current_step"] == TripLookupStep.WAITING_FOR_TRIP_RESULT


@pytest.mark.asyncio
async def test_trip_lookup_reports_only_validated_tool_data():
    workflow = TripLookupWorkflow()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
    )
    call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="GSM-12345"),
        state,
    )
    state = apply_action(state, call)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.LOOKUP_TRIP,
                call_id=call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "found": True,
                    "booking_id": "GSM-12345",
                    "status": "Đang đến điểm đón",
                    "eta_minutes": 4,
                },
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert "Đang đến điểm đón" in action.message
    assert "4 phút" in action.message
    assert action.state_updates["current_workflow"] is None
    data = TripLookupData.model_validate(
        action.state_updates["collected_data"]["trip_lookup"]
    )
    assert data.trip_status == "Đang đến điểm đón"


@pytest.mark.asyncio
async def test_trip_lookup_not_found_asks_for_another_identifier():
    workflow = TripLookupWorkflow()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
    )
    call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="GSM-12345"),
        state,
    )
    state = apply_action(state, call)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.LOOKUP_TRIP,
                call_id=call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={"found": False},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == TripLookupStep.COLLECT_IDENTIFIER
    assert action.state_updates["pending_tool_call_id"] is None
    assert action.state_updates["retry_count"] == 1


@pytest.mark.asyncio
async def test_trip_lookup_retries_retryable_tool_error():
    workflow = TripLookupWorkflow()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
    )
    call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="GSM-12345"),
        state,
    )
    state = apply_action(state, call)

    retry = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.LOOKUP_TRIP,
                call_id=call.tool_call.call_id,
                status=ToolStatus.ERROR,
                error="trip service timeout",
                error_code="TIMEOUT",
                retryable=True,
            ),
        ),
        state,
    )

    assert retry.action_type is ActionType.CALL_TOOL
    assert retry.tool_call is not None
    assert retry.tool_call.call_id != call.tool_call.call_id
    assert retry.state_updates["retry_count"] == 1


@pytest.mark.asyncio
async def test_trip_lookup_handoffs_on_critical_or_mismatched_result():
    workflow = TripLookupWorkflow()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.WAITING_FOR_TRIP_RESULT,
        collected_data={
            "trip_lookup": TripLookupData(booking_id="GSM-12345").model_dump(
                mode="json"
            )
        },
        pending_tool_call_id="expected-call",
        pending_tool_name=ToolName.LOOKUP_TRIP,
    )

    critical = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.LOOKUP_TRIP,
                call_id="expected-call",
                status=ToolStatus.ERROR,
                error="database unavailable",
                retryable=False,
            ),
        ),
        state,
    )
    mismatched = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.LOOKUP_TRIP,
                call_id="wrong-call",
                status=ToolStatus.SUCCESS,
                data={"found": False},
            ),
        ),
        state,
    )

    assert critical.action_type is ActionType.HANDOFF
    assert mismatched.action_type is ActionType.HANDOFF
    assert critical.state_updates["current_workflow"] is WorkflowType.HUMAN_HANDOFF
