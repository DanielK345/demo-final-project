import pytest
from pydantic import ValidationError

from src.agents.booking_types import VehicleType
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolCall,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.tools.booking import (
    CancelBookingTool,
    CreateBookingTool,
    EstimateFareTool,
    GetVehicleOptionsTool,
)
from src.agents.tools.call_id import build_call_id
from src.agents.tools.handoff import CreateHandoffTool
from src.agents.tools.knowledge import RetrieveKnowledgeTool
from src.agents.tools.lifecycle import (
    ToolResultMismatchError,
    ToolResultPayloadError,
    UnexpectedToolResultError,
    clear_pending_tool_updates,
    correlate_tool_result,
    normalize_tool_failure,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.maps import SearchPlaceTool
from src.agents.tools.schemas import SearchPlaceResult
from src.agents.tools.trip import LookupTripTool


def test_tool_builds_contract_without_executing_side_effect():
    call = SearchPlaceTool().build_call("call-001", query="Times City")

    assert call.tool_name == ToolName.SEARCH_PLACE
    assert call.params == {"query": "Times City"}


def test_trip_lookup_requires_an_identifier():
    with pytest.raises(ValidationError):
        LookupTripTool().build_call("call-002")


@pytest.mark.parametrize(
    ("tool", "params"),
    [
        (
            CreateBookingTool(),
            {
                "pickup_place_id": "pickup-1",
                "destination_place_id": "destination-1",
                "phone_number": "0900000000",
                "vehicle_type": VehicleType.CAR_4,
                "fare_estimate_id": "fare-001",
                "idempotency_key": "booking-key-001",
            },
        ),
        (
            EstimateFareTool(),
            {
                "pickup_place_id": "pickup-1",
                "destination_place_id": "destination-1",
                "vehicle_type": VehicleType.MOTORBIKE,
            },
        ),
        (
            GetVehicleOptionsTool(),
            {
                "pickup_place_id": "pickup-1",
                "destination_place_id": "destination-1",
                "passenger_count": 3,
                "luggage_count": 2,
                "preference": "comfortable",
            },
        ),
        (
            CancelBookingTool(),
            {
                "booking_id": "booking-001",
                "idempotency_key": "cancel-key-001",
            },
        ),
        (RetrieveKnowledgeTool(), {"query": "Giá cước là bao nhiêu?"}),
        (
            CreateHandoffTool(),
            {
                "session_id": "session-001",
                "reason": "USER_REQUEST",
                "context": {},
            },
        ),
    ],
)
def test_tool_builders_validate_and_preserve_typed_params(tool, params):
    call = tool.build_call("call-001", **params)

    assert call.params == params


def test_tool_params_reject_blank_required_text():
    with pytest.raises(ValidationError):
        SearchPlaceTool().build_call("call-001", query="   ")


def test_create_booking_rejects_invalid_mobile_phone():
    with pytest.raises(ValidationError, match="valid Vietnamese mobile"):
        CreateBookingTool().build_call(
            "call-001",
            pickup_place_id="pickup-1",
            destination_place_id="destination-1",
            phone_number="0123456789",
            vehicle_type=VehicleType.CAR_4,
            fare_estimate_id="fare-001",
            idempotency_key="booking-key-001",
        )


def test_call_tool_action_requires_tool_call():
    with pytest.raises(ValidationError):
        AgentAction(action_type=ActionType.CALL_TOOL)


@pytest.mark.parametrize(
    "action_type",
    [ActionType.ASK_USER, ActionType.RESPOND, ActionType.HANDOFF, ActionType.END_SESSION],
)
def test_customer_facing_actions_require_a_message(action_type):
    with pytest.raises(ValidationError, match="require a message"):
        AgentAction(action_type=action_type)


def test_input_accepts_tool_result_with_transcript_for_callback_priority():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    agent_input = AgentInput(
        session_id="session-001",
        turn_id="turn-001",
        transcript="khẩn cấp",
        tool_result=result,
        stt_confidence=0.2,
    )

    assert agent_input.tool_result is result


def test_shared_identifiers_reject_blank_values():
    with pytest.raises(ValidationError, match="identity cannot be blank"):
        AgentInput(session_id="   ", turn_id="turn-001", transcript="hello")

    with pytest.raises(ValidationError, match="identity cannot be blank"):
        ToolCall(tool_name=ToolName.SEARCH_PLACE, call_id="   ")

    with pytest.raises(ValidationError, match="identity cannot be blank"):
        ToolResult(
            tool_name=ToolName.SEARCH_PLACE,
            call_id="   ",
            status=ToolStatus.SUCCESS,
        )


def test_failed_tool_result_requires_error_details():
    with pytest.raises(ValidationError):
        ToolResult(
            tool_name=ToolName.LOOKUP_TRIP,
            call_id="call-003",
            status=ToolStatus.ERROR,
        )


def test_successful_tool_result_rejects_error_metadata():
    with pytest.raises(ValidationError):
        ToolResult(
            tool_name=ToolName.LOOKUP_TRIP,
            call_id="call-003",
            status=ToolStatus.SUCCESS,
            error_code="TIMEOUT",
        )


def test_build_call_id_is_correlatable_and_validated():
    call_id = build_call_id(
        session_id="session-001",
        workflow=WorkflowType.RIDE_BOOKING,
        tool_name=ToolName.SEARCH_PLACE,
        operation="pickup",
        sequence=2,
    )

    assert call_id == "session-001:ride_booking:search_place:pickup:2"

    with pytest.raises(ValueError, match="unsupported characters"):
        build_call_id(
            session_id="session:001",
            workflow=WorkflowType.RIDE_BOOKING,
            tool_name=ToolName.SEARCH_PLACE,
            operation="pickup",
            sequence=2,
        )


def _pending_state(
    *,
    call_id: str = "call-001",
    tool_name: ToolName = ToolName.SEARCH_PLACE,
) -> AgentState:
    return AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_PLACE",
        pending_tool_call_id=call_id,
        pending_tool_name=tool_name,
    )


def test_pending_tool_updates_open_and_clear_lifecycle():
    call = ToolCall(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        params={"query": "Times City"},
    )

    assert pending_tool_updates(call, waiting_step="WAITING_FOR_PLACE") == {
        "current_step": "WAITING_FOR_PLACE",
        "pending_tool_call_id": "call-001",
        "pending_tool_name": ToolName.SEARCH_PLACE,
    }
    assert clear_pending_tool_updates() == {
        "pending_tool_call_id": None,
        "pending_tool_name": None,
    }


def test_correlate_tool_result_accepts_expected_result():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    correlate_tool_result(result, _pending_state())


def test_correlate_tool_result_rejects_unexpected_or_mismatched_result():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    with pytest.raises(UnexpectedToolResultError):
        correlate_tool_result(result, AgentState(session_id="session-001"))

    with pytest.raises(ToolResultMismatchError, match="call_id"):
        correlate_tool_result(result, _pending_state(call_id="call-002"))

    with pytest.raises(ToolResultMismatchError, match="name"):
        correlate_tool_result(
            result,
            _pending_state(tool_name=ToolName.CREATE_BOOKING),
        )


def test_parse_tool_result_returns_typed_payload():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.SUCCESS,
        data={
            "candidates": [
                {
                    "place_id": "place-1",
                    "display_name": "Times City",
                    "address": "458 Minh Khai",
                }
            ]
        },
    )

    payload = parse_tool_result(result, _pending_state())

    assert isinstance(payload, SearchPlaceResult)
    assert payload.candidates[0].place_id == "place-1"


def test_parse_tool_result_rejects_invalid_payload():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.SUCCESS,
        data={"candidates": [{"display_name": "Times City"}]},
    )

    with pytest.raises(ToolResultPayloadError):
        parse_tool_result(result, _pending_state())


def test_normalize_tool_failure_preserves_retry_policy():
    result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-001",
        status=ToolStatus.ERROR,
        error="maps timeout",
        error_code="TIMEOUT",
        retryable=True,
    )

    failure = normalize_tool_failure(result, _pending_state())

    assert failure.code == "TIMEOUT"
    assert failure.retryable is True
    assert failure.message == "maps timeout"
