from src.agents.contracts.schemas import ActionType, AgentAction, ToolCall, ToolName, WorkflowType
from src.agents.contracts.state import AgentState, ConfirmationStatus
from src.agents.core.booking.state import BookingData, BookingStep
from src.agents.tools.builders import (
    CancelBookingTool,
    CreateBookingTool,
    EstimateFareTool,
    GetVehicleOptionsTool,
    SearchPlaceTool,
)
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import pending_tool_updates


def request_place_action(
    state: AgentState,
    data: BookingData,
    tool: SearchPlaceTool,
    *,
    query: str,
    operation: str,
    waiting_step: BookingStep,
) -> AgentAction:
    call_id = _call_id(state, ToolName.SEARCH_PLACE, operation)
    tool_call = tool.build_call(call_id, query=query)
    return _call_tool_action(
        state,
        data,
        tool_call,
        waiting_step=waiting_step,
        reason=f"The {operation} location must be resolved.",
    )


def request_vehicle_options_action(
    state: AgentState,
    data: BookingData,
    tool: GetVehicleOptionsTool,
) -> AgentAction:
    assert data.pickup is not None
    assert data.destination is not None
    assert data.passenger_count is not None
    call_id = _call_id(state, ToolName.GET_VEHICLE_OPTIONS, "vehicle-options")
    tool_call = tool.build_call(
        call_id,
        pickup_place_id=data.pickup.place_id,
        destination_place_id=data.destination.place_id,
        passenger_count=data.passenger_count,
        luggage_count=data.luggage_count,
        preference=data.vehicle_preference,
    )
    return _call_tool_action(
        state,
        data,
        tool_call,
        waiting_step=BookingStep.WAITING_FOR_VEHICLE_OPTIONS,
        reason="Backend options are required before recommending a vehicle.",
    )


def request_fare_estimate_action(
    state: AgentState,
    data: BookingData,
    tool: EstimateFareTool,
) -> AgentAction:
    assert data.pickup is not None
    assert data.destination is not None
    assert data.vehicle_type is not None
    call_id = _call_id(state, ToolName.ESTIMATE_FARE, "fare")
    tool_call = tool.build_call(
        call_id,
        pickup_place_id=data.pickup.place_id,
        destination_place_id=data.destination.place_id,
        vehicle_type=data.vehicle_type,
    )
    return _call_tool_action(
        state,
        data,
        tool_call,
        waiting_step=BookingStep.WAITING_FOR_FARE_ESTIMATE,
        reason="A current fare estimate is required before booking confirmation.",
    )


def request_create_booking_action(
    state: AgentState,
    data: BookingData,
    tool: CreateBookingTool,
    *,
    idempotency_key: str,
) -> AgentAction:
    assert data.pickup is not None
    assert data.destination is not None
    assert data.vehicle_type is not None
    assert data.fare_estimate_id is not None
    assert data.phone_number is not None
    call_id = _call_id(state, ToolName.CREATE_BOOKING, "booking")
    tool_call = tool.build_call(
        call_id,
        pickup_place_id=data.pickup.place_id,
        destination_place_id=data.destination.place_id,
        phone_number=data.phone_number,
        vehicle_type=data.vehicle_type,
        vehicle_option_id=data.selected_vehicle_option_id,
        fare_estimate_id=data.fare_estimate_id,
        idempotency_key=idempotency_key,
        passenger_count=data.passenger_count,
    )
    return _call_tool_action(
        state,
        data,
        tool_call,
        waiting_step=BookingStep.WAITING_FOR_BOOKING_RESULT,
        reason="The user explicitly confirmed the booking.",
        confirmation=ConfirmationStatus.CONFIRMED,
        reset_retry=False,
    )


def request_cancel_booking_action(
    state: AgentState,
    data: BookingData,
    tool: CancelBookingTool,
    *,
    idempotency_key: str,
) -> AgentAction:
    assert data.booking_id is not None
    call_id = _call_id(state, ToolName.CANCEL_BOOKING, "cancel")
    tool_call = tool.build_call(
        call_id,
        booking_id=data.booking_id,
        idempotency_key=idempotency_key,
    )
    return _call_tool_action(
        state,
        data,
        tool_call,
        waiting_step=BookingStep.WAITING_FOR_CANCELLATION_RESULT,
        reason="The user explicitly confirmed booking cancellation.",
        confirmation=ConfirmationStatus.CONFIRMED,
        include_booking_data=False,
        reset_retry=False,
    )


def _call_id(state: AgentState, tool_name: ToolName, operation: str) -> str:
    return build_call_id(
        session_id=state.session_id,
        workflow=WorkflowType.RIDE_BOOKING,
        tool_name=tool_name,
        operation=operation,
        sequence=state.state_version + 1,
    )


def _call_tool_action(
    state: AgentState,
    data: BookingData,
    tool_call: ToolCall,
    *,
    waiting_step: BookingStep,
    reason: str,
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED,
    include_booking_data: bool = True,
    reset_retry: bool = True,
) -> AgentAction:
    updates: dict[str, object] = {
        "current_workflow": WorkflowType.RIDE_BOOKING,
        "confirmation": confirmation,
        **pending_tool_updates(tool_call, waiting_step=waiting_step.value),
    }
    if reset_retry:
        updates["retry_count"] = 0
    if include_booking_data:
        collected_data = dict(state.collected_data)
        collected_data["booking"] = data.model_dump(mode="json")
        updates["collected_data"] = collected_data
    return AgentAction(
        action_type=ActionType.CALL_TOOL,
        tool_call=tool_call,
        state_updates=updates,
        reason=reason,
    )
