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
from src.agents.understanding.models import (
    Correction,
    CorrectionField,
    UnderstandingResult,
)
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
        collected_data={"booking": (data or BookingData()).model_dump(mode="json")},
        confirmation=confirmation,
    )


@pytest.mark.asyncio
async def test_booking_starts_by_asking_for_pickup():
    action = await RideBookingWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Tôi muốn đặt xe"),
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
            turn_id="turn-001",
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
@pytest.mark.parametrize("location", ["nhà", "về nhà tôi", "ở đó", "chỗ cũ"])
async def test_booking_requires_concrete_address_for_ambiguous_location(location):
    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript=location,
        ),
        booking_state(step=BookingStep.COLLECT_DESTINATION),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.tool_call is None
    assert action.state_updates["current_step"] == BookingStep.COLLECT_DESTINATION
    assert "địa chỉ điểm đến cụ thể" in (action.message or "").casefold()


@pytest.mark.asyncio
async def test_booking_handles_zero_place_candidates():
    workflow = RideBookingWorkflow()
    state = booking_state(step=BookingStep.COLLECT_PICKUP)
    call_action = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Một nơi không rõ"),
        state,
    )
    waiting = apply_action(state, call_action)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
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
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Hồ Gươm"),
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
            turn_id="turn-001",
            tool_result=place_result(call_action.tool_call.call_id, candidates),
        ),
        waiting,
    )
    selecting = apply_action(waiting, ask)
    selected = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Số 2"),
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
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Tôi muốn đặt xe"),
        state,
    )
    state = apply_action(state, ask_pickup)
    pickup_call = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Hồ Gươm"),
        state,
    )
    assert pickup_call.tool_call is not None
    assert pickup_call.tool_call.tool_name is ToolName.SEARCH_PLACE
    state = apply_action(state, pickup_call)

    ask_destination = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
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
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Times City"),
        state,
    )
    assert destination_call.tool_call is not None
    assert destination_call.tool_call.tool_name is ToolName.SEARCH_PLACE
    state = apply_action(state, destination_call)

    ask_phone = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=place_result(
                destination_call.tool_call.call_id,
                [{"place_id": "destination-1", "display_name": "Times City"}],
            ),
        ),
        state,
    )
    assert ask_phone.action_type is ActionType.ASK_USER
    assert ask_phone.state_updates["current_step"] == BookingStep.COLLECT_VEHICLE_TYPE
    state = apply_action(state, ask_phone)

    ask_phone_number = await workflow.handle(
        AgentInput(session_id="session-001", transcript="xe 4 chỗ"),
        state,
    )
    assert ask_phone_number.action_type is ActionType.ASK_USER
    assert ask_phone_number.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    state = apply_action(state, ask_phone_number)

    confirmation = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="0901234567"),
        state,
    )
    assert confirmation.action_type is ActionType.ASK_USER
    assert confirmation.state_updates["current_step"] == BookingStep.CONFIRM
    assert confirmation.state_updates["confirmation"] is ConfirmationStatus.AWAITING_CONFIRMATION
    state = apply_action(state, confirmation)

    booking_call = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Đúng, đặt giúp tôi"),
        state,
    )
    assert booking_call.action_type is ActionType.CALL_TOOL
    assert booking_call.tool_call is not None
    assert booking_call.tool_call.tool_name is ToolName.CREATE_BOOKING
    assert booking_call.tool_call.params == {
        "pickup_place_id": "pickup-1",
        "destination_place_id": "destination-1",
        "phone_number": "0901234567",
    }
    state = apply_action(state, booking_call)

    completed = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
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
            "phone_number": "0901234567",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    action = await RideBookingWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Ừm để xem"),
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
            "phone_number": "0901234567",
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
            turn_id="turn-001",
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
async def test_explicit_raw_correction_field_overrides_conflicting_understanding():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "phone_number": "0901234567",
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
            turn_id="turn-001",
            transcript="Đổi điểm đón sang Nhà hát Lớn",
        ),
        state,
        UnderstandingResult(
            corrections=[
                Correction(
                    field=CorrectionField.DESTINATION,
                    value="Royal City",
                )
            ]
        ),
    )

    corrected = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )
    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.params == {"query": "Nhà hát Lớn"}
    assert corrected.correction_field is CorrectionField.PICKUP
    assert corrected.pickup is None
    assert corrected.destination is not None


@pytest.mark.asyncio
async def test_pickup_correction_returns_to_confirmation_without_losing_other_fields():
    workflow = RideBookingWorkflow()
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "destination_query": "Times City",
            "phone_number": "0901234567",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    search = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Không, đổi điểm đón sang Nhà hát Lớn",
        ),
        state,
    )
    waiting = apply_action(state, search)
    corrected = BookingData.model_validate(
        search.state_updates["collected_data"]["booking"]
    )

    assert search.action_type is ActionType.CALL_TOOL
    assert search.tool_call is not None
    assert search.tool_call.params == {"query": "Nhà hát Lớn"}
    assert corrected.correction_field is CorrectionField.PICKUP
    assert corrected.correction_return_step is BookingStep.CONFIRM
    assert corrected.destination is not None
    assert corrected.destination.place_id == "d1"
    assert corrected.phone_number == "0901234567"

    confirmation = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            tool_result=place_result(
                search.tool_call.call_id,
                [{"place_id": "p2", "display_name": "Nhà hát Lớn"}],
            ),
        ),
        waiting,
    )
    final_data = BookingData.model_validate(
        confirmation.state_updates["collected_data"]["booking"]
    )

    assert confirmation.action_type is ActionType.ASK_USER
    assert confirmation.state_updates["current_step"] == BookingStep.CONFIRM
    assert confirmation.state_updates["confirmation"] is ConfirmationStatus.AWAITING_CONFIRMATION
    assert "Nhà hát Lớn" in (confirmation.message or "")
    assert "Times City" in (confirmation.message or "")
    assert final_data.pickup is not None
    assert final_data.pickup.place_id == "p2"
    assert final_data.destination is not None
    assert final_data.destination.place_id == "d1"
    assert final_data.phone_number == "0901234567"
    assert final_data.correction_field is None
    assert final_data.correction_return_step is None


@pytest.mark.asyncio
async def test_destination_correction_without_value_asks_only_for_new_destination():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "phone_number": "0901234567",
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
            turn_id="turn-001",
            transcript="Sửa điểm đến",
        ),
        state,
    )
    corrected = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.COLLECT_DESTINATION
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED
    assert action.state_updates["retry_count"] == 0
    assert "địa chỉ nào" in (action.message or "")
    assert corrected.destination is None
    assert corrected.pickup is not None
    assert corrected.phone_number == "0901234567"
    assert corrected.correction_field is CorrectionField.DESTINATION


@pytest.mark.asyncio
async def test_phone_correction_updates_phone_and_requires_fresh_confirmation():
    workflow = RideBookingWorkflow()
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "phone_number": "0901234567",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    correction = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Số điện thoại đúng là 0987654321",
        ),
        state,
    )
    corrected_state = apply_action(state, correction)
    corrected = BookingData.model_validate(
        correction.state_updates["collected_data"]["booking"]
    )

    assert correction.action_type is ActionType.ASK_USER
    assert correction.tool_call is None
    assert correction.state_updates["current_step"] == BookingStep.CONFIRM
    assert (
        correction.state_updates["confirmation"]
        is ConfirmationStatus.AWAITING_CONFIRMATION
    )
    assert corrected.phone_number == "0987654321"
    assert corrected.pickup is not None
    assert corrected.destination is not None

    booking_call = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Đúng, đặt giúp tôi",
        ),
        corrected_state,
    )

    assert booking_call.action_type is ActionType.CALL_TOOL
    assert booking_call.tool_call is not None
    assert booking_call.tool_call.params["phone_number"] == "0987654321"


@pytest.mark.asyncio
async def test_generic_correction_asks_for_field_then_preserves_return_to_confirmation():
    workflow = RideBookingWorkflow()
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "phone_number": "0901234567",
        }
    )
    state = booking_state(
        step=BookingStep.CONFIRM,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    choose = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi muốn sửa lại thông tin",
        ),
        state,
    )
    choosing_state = apply_action(state, choose)
    selected = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Số điện thoại",
        ),
        choosing_state,
    )
    selected_data = BookingData.model_validate(
        selected.state_updates["collected_data"]["booking"]
    )

    assert choose.action_type is ActionType.ASK_USER
    assert choose.state_updates["current_step"] == BookingStep.SELECT_CORRECTION_FIELD
    assert choose.state_updates["confirmation"] is ConfirmationStatus.REJECTED
    assert selected.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    assert selected_data.correction_field is CorrectionField.PHONE_NUMBER
    assert selected_data.correction_return_step is BookingStep.CONFIRM
    assert selected_data.pickup is not None
    assert selected_data.destination is not None


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
            turn_id="turn-001",
            tool_result=place_result("wrong-call", []),
        ),
        state,
    )
    failed = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
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
