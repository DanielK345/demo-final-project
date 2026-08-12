import pytest

from src.agents.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.workflows.booking import RideBookingWorkflow
from src.agents.workflows.booking_models import BookingData, BookingStep


def apply_action(state: AgentState, action) -> AgentState:
    return state.apply(action.state_updates)


def place_result(call_id: str, candidates: list[dict]) -> ToolResult:
    return ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id=call_id,
        status=ToolStatus.SUCCESS,
        data={"candidates": candidates},
    )


def booking_state(
    *,
    step: BookingStep,
    data: BookingData | None = None,
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED,
) -> AgentState:
    return AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=step.value,
        collected_data={
            "booking": (data or BookingData()).model_dump(mode="json")
        },
        confirmation=confirmation,
    )


@pytest.mark.asyncio
async def test_booking_starts_by_asking_for_pickup():
    action = await RideBookingWorkflow().handle(
        AgentInput(session_id="session-001", transcript="Tôi muốn đặt xe"),
        AgentState(session_id="session-001"),
    )

    assert action.action_type is ActionType.ASK_USER
    assert "điểm đón" in action.message
    assert action.state_updates["current_step"] == BookingStep.COLLECT_PICKUP


@pytest.mark.asyncio
async def test_booking_extracts_route_and_resolves_pickup_first():
    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id="session-001",
            transcript="Đặt xe từ Hồ Gươm đến Times City",
        ),
        AgentState(session_id="session-001"),
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert action.tool_call.params == {"query": "Hồ Gươm"}
    assert action.state_updates["current_step"] == BookingStep.WAITING_FOR_PICKUP_RESULT
    data = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert data.destination_query == "Times City"


@pytest.mark.asyncio
async def test_booking_handles_zero_place_candidates():
    workflow = RideBookingWorkflow()
    state = booking_state(step=BookingStep.COLLECT_PICKUP)
    call_action = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Một nơi không rõ"),
        state,
    )
    waiting = apply_action(state, call_action)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=place_result(call_action.tool_call.call_id, []),
        ),
        waiting,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.COLLECT_PICKUP
    assert action.state_updates["retry_count"] == 1
    assert action.state_updates["pending_tool_call_id"] is None


@pytest.mark.asyncio
async def test_booking_requires_user_to_select_ambiguous_place():
    workflow = RideBookingWorkflow()
    state = booking_state(step=BookingStep.COLLECT_PICKUP)
    call_action = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Hồ Gươm"),
        state,
    )
    waiting = apply_action(state, call_action)
    candidates = [
        {"place_id": "p1", "display_name": "Hồ Hoàn Kiếm"},
        {"place_id": "p2", "display_name": "Phố Lê Thái Tổ"},
    ]

    ask = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=place_result(call_action.tool_call.call_id, candidates),
        ),
        waiting,
    )
    selecting = apply_action(waiting, ask)
    selected = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Số 2"),
        selecting,
    )

    assert ask.action_type is ActionType.ASK_USER
    assert ask.state_updates["current_step"] == BookingStep.SELECT_PICKUP_CANDIDATE
    assert selected.state_updates["current_step"] == BookingStep.COLLECT_DESTINATION
    data = BookingData.model_validate(selected.state_updates["collected_data"]["booking"])
    assert data.pickup is not None
    assert data.pickup.place_id == "p2"


@pytest.mark.asyncio
async def test_booking_happy_path_requires_confirmation_before_create_booking():
    workflow = RideBookingWorkflow()
    state = AgentState(session_id="session-001")

    ask_pickup = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Tôi muốn đặt xe"),
        state,
    )
    state = apply_action(state, ask_pickup)
    pickup_call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Hồ Gươm"),
        state,
    )
    assert pickup_call.tool_call is not None
    assert pickup_call.tool_call.tool_name is ToolName.SEARCH_PLACE
    state = apply_action(state, pickup_call)

    ask_destination = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=place_result(
                pickup_call.tool_call.call_id,
                [{"place_id": "pickup-1", "display_name": "Hồ Gươm"}],
            ),
        ),
        state,
    )
    assert ask_destination.action_type is ActionType.ASK_USER
    state = apply_action(state, ask_destination)

    destination_call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Times City"),
        state,
    )
    assert destination_call.tool_call is not None
    assert destination_call.tool_call.tool_name is ToolName.SEARCH_PLACE
    state = apply_action(state, destination_call)

    ask_vehicle = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=place_result(
                destination_call.tool_call.call_id,
                [{"place_id": "destination-1", "display_name": "Times City"}],
            ),
        ),
        state,
    )
    assert ask_vehicle.action_type is ActionType.ASK_USER
    assert ask_vehicle.state_updates["current_step"] == BookingStep.COLLECT_VEHICLE_TYPE
    state = apply_action(state, ask_vehicle)

    confirmation = await workflow.handle(
        AgentInput(session_id="session-001", transcript="xe 4 chỗ"),
        state,
    )
    assert confirmation.action_type is ActionType.ASK_USER
    assert confirmation.state_updates["current_step"] == BookingStep.CONFIRM
    assert (
        confirmation.state_updates["confirmation"]
        is ConfirmationStatus.AWAITING_CONFIRMATION
    )
    state = apply_action(state, confirmation)

    booking_call = await workflow.handle(
        AgentInput(session_id="session-001", transcript="Đúng, đặt giúp tôi"),
        state,
    )
    assert booking_call.action_type is ActionType.CALL_TOOL
    assert booking_call.tool_call is not None
    assert booking_call.tool_call.tool_name is ToolName.CREATE_BOOKING
    assert booking_call.tool_call.params == {
        "pickup_place_id": "pickup-1",
        "destination_place_id": "destination-1",
        "phone_number": "authenticated_account",
    }
    state = apply_action(state, booking_call)

    completed = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.CREATE_BOOKING,
                call_id=booking_call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "booking_id": "booking-001",
                    "status": "CONFIRMED",
                    "eta_minutes": 5,
                },
            ),
        ),
        state,
    )

    assert completed.action_type is ActionType.RESPOND
    assert "5 phút" in completed.message
    assert completed.state_updates["current_workflow"] is None
    assert completed.state_updates["pending_tool_call_id"] is None
    data = BookingData.model_validate(completed.state_updates["collected_data"]["booking"])
    assert data.booking_id == "booking-001"


@pytest.mark.asyncio
async def test_booking_does_not_create_booking_for_unclear_confirmation():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "p2", "display_name": "Times City"},
            "vehicle_type": "4_SEAT",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    action = await RideBookingWorkflow().handle(
        AgentInput(session_id="session-001", transcript="Ừm để xem"),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.tool_call is None
    assert action.state_updates["retry_count"] == 1


@pytest.mark.asyncio
async def test_booking_correction_resets_confirmation_and_resolves_again():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "p2", "display_name": "Times City"},
            "vehicle_type": "4_SEAT",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id="session-001",
            transcript="Đổi điểm đến thành Royal City",
        ),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.params == {"query": "Royal City"}
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED
    data = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert data.destination is None


@pytest.mark.asyncio
async def test_booking_handoffs_on_mismatched_or_failed_tool_result():
    workflow = RideBookingWorkflow()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
        pending_tool_call_id="expected-call",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    mismatched = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=place_result("wrong-call", []),
        ),
        state,
    )
    failed = await workflow.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="expected-call",
                status=ToolStatus.ERROR,
                error="maps unavailable",
                error_code="UNAVAILABLE",
                retryable=False,
            ),
        ),
        state,
    )

    assert mismatched.action_type is ActionType.HANDOFF
    assert failed.action_type is ActionType.HANDOFF
    assert failed.state_updates["current_workflow"] is WorkflowType.HUMAN_HANDOFF
