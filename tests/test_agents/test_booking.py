import pytest

from src.agents.agent import LLMAgent
from src.agents.booking_types import VehicleType
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
from src.agents.vehicle_recommendation import (
    RecommendationReason,
    VehicleRecommendation,
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


def fare_result(call_id: str, amount: float = 75000) -> ToolResult:
    return ToolResult(
        tool_name=ToolName.ESTIMATE_FARE,
        call_id=call_id,
        status=ToolStatus.SUCCESS,
        data={
            "estimate_id": "fare-001",
            "fare_amount": amount,
            "currency": "VND",
            "eta_minutes": 6,
            "distance_km": 12.5,
        },
    )


class StubVehicleRecommender:
    async def recommend(self, **kwargs):
        del kwargs
        return VehicleRecommendation(
            option_id="car-7",
            reason=RecommendationReason.COMFORT,
        )


def booking_state(
    *,
    step: BookingStep,
    data: BookingData | None = None,
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED,
) -> AgentState:
    booking_data = data or BookingData()
    if step is BookingStep.CONFIRM:
        values = booking_data.model_dump()
        values["vehicle_type"] = values["vehicle_type"] or VehicleType.CAR_4
        values["fare_estimate_id"] = values["fare_estimate_id"] or "fare-001"
        values["estimated_fare_amount"] = (
            values["estimated_fare_amount"] or 75000
        )
        values["estimated_currency"] = values["estimated_currency"] or "VND"
        booking_data = BookingData.model_validate(values)
    return AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=step.value,
        collected_data={"booking": booking_data.model_dump(mode="json")},
        confirmation=confirmation,
    )


@pytest.mark.asyncio
async def test_booking_starts_by_asking_for_pickup():
    action = await RideBookingWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Tôi muốn đặt xe"),
        AgentState(session_id="session-001"),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.message == "Bạn muốn đón ở đâu?"
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

    ask_vehicle = await workflow.handle(
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
    assert ask_vehicle.action_type is ActionType.ASK_USER
    assert ask_vehicle.state_updates["current_step"] == BookingStep.COLLECT_VEHICLE
    state = apply_action(state, ask_vehicle)

    fare_call = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Ô tô 4 chỗ",
        ),
        state,
    )
    assert fare_call.action_type is ActionType.CALL_TOOL
    assert fare_call.tool_call is not None
    assert fare_call.tool_call.tool_name is ToolName.ESTIMATE_FARE
    state = apply_action(state, fare_call)

    ask_phone = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=fare_result(fare_call.tool_call.call_id),
        ),
        state,
    )
    assert ask_phone.action_type is ActionType.ASK_USER
    assert ask_phone.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    assert "75.000 đồng" in (ask_phone.message or "")
    state = apply_action(state, ask_phone)

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
        "vehicle_type": "CAR_4",
        "fare_estimate_id": "fare-001",
        "idempotency_key": booking_call.tool_call.params["idempotency_key"],
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

    fare_call = await workflow.handle(
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
    assert fare_call.action_type is ActionType.CALL_TOOL
    assert fare_call.tool_call is not None
    assert fare_call.tool_call.tool_name is ToolName.ESTIMATE_FARE

    confirmation = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-003",
            tool_result=fare_result(fare_call.tool_call.call_id),
        ),
        apply_action(waiting, fare_call),
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


@pytest.mark.asyncio
async def test_booking_rejects_same_resolved_pickup_and_destination():
    workflow = RideBookingWorkflow()
    data = BookingData(
        pickup={"place_id": "same-place", "display_name": "VinUniversity"},
        destination_query="VinUniversity",
    )
    state = booking_state(
        step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
        data=data,
    ).model_copy(
        update={
            "pending_tool_call_id": "destination-call",
            "pending_tool_name": ToolName.SEARCH_PLACE,
        }
    )

    action = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-same-route",
            tool_result=place_result(
                "destination-call",
                [{"place_id": "same-place", "display_name": "VinUniversity"}],
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.COLLECT_DESTINATION
    assert "phải khác" in (action.message or "")
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )
    assert updated.destination is None
    assert updated.fare_estimate_id is None


@pytest.mark.asyncio
async def test_user_can_supersede_pending_destination_search():
    workflow = RideBookingWorkflow()
    data = BookingData(
        pickup={"place_id": "p1", "display_name": "VinUniversity"},
        destination_query="Times City",
    )
    state = booking_state(
        step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
        data=data,
    ).model_copy(
        update={
            "pending_tool_call_id": "old-search",
            "pending_tool_name": ToolName.SEARCH_PLACE,
        }
    )

    action = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-new-address",
            transcript="Royal City",
        ),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.params == {"query": "Royal City"}
    assert action.tool_call.call_id != "old-search"
    assert action.state_updates["pending_tool_call_id"] == action.tool_call.call_id


@pytest.mark.asyncio
async def test_retryable_place_failure_retries_but_critical_failure_handoffs():
    workflow = RideBookingWorkflow()
    data = BookingData(pickup_query="VinUniversity")
    state = booking_state(
        step=BookingStep.WAITING_FOR_PICKUP_RESULT,
        data=data,
    ).model_copy(
        update={
            "pending_tool_call_id": "search-call",
            "pending_tool_name": ToolName.SEARCH_PLACE,
        }
    )

    retry = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-retry",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="search-call",
                status=ToolStatus.ERROR,
                error="maps timeout",
                error_code="TIMEOUT",
                retryable=True,
            ),
        ),
        state,
    )
    critical = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-critical",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="search-call",
                status=ToolStatus.ERROR,
                error="invalid credentials",
                error_code="UNAUTHORIZED",
            ),
        ),
        state,
    )

    assert retry.action_type is ActionType.CALL_TOOL
    assert retry.state_updates["retry_count"] == 1
    assert critical.action_type is ActionType.HANDOFF


@pytest.mark.asyncio
async def test_unknown_booking_outcome_requires_reconciliation_and_keeps_pending_call():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "vehicle_type": "CAR_4",
            "fare_estimate_id": "fare-001",
            "phone_number": "0901234567",
        }
    )
    state = booking_state(
        step=BookingStep.WAITING_FOR_BOOKING_RESULT,
        data=data,
        confirmation=ConfirmationStatus.CONFIRMED,
    ).model_copy(
        update={
            "pending_tool_call_id": "booking-call",
            "pending_tool_name": ToolName.CREATE_BOOKING,
        }
    )

    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-timeout",
            tool_result=ToolResult(
                tool_name=ToolName.CREATE_BOOKING,
                call_id="booking-call",
                status=ToolStatus.ERROR,
                error="connection closed before response",
                error_code="UNKNOWN_OUTCOME",
                retryable=True,
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.state_updates["current_step"] == "RECONCILIATION_REQUIRED"
    assert "pending_tool_call_id" not in action.state_updates
    assert "pending_tool_name" not in action.state_updates


@pytest.mark.asyncio
async def test_stale_booking_result_requires_reconciliation_without_clearing_pending():
    state = booking_state(
        step=BookingStep.WAITING_FOR_BOOKING_RESULT,
        confirmation=ConfirmationStatus.CONFIRMED,
    ).model_copy(
        update={
            "pending_tool_call_id": "current-booking-call",
            "pending_tool_name": ToolName.CREATE_BOOKING,
        }
    )

    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-stale",
            tool_result=ToolResult(
                tool_name=ToolName.CREATE_BOOKING,
                call_id="stale-booking-call",
                status=ToolStatus.SUCCESS,
                data={"booking_id": "booking-old", "status": "CONFIRMED"},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.state_updates["current_step"] == "RECONCILIATION_REQUIRED"
    assert "pending_tool_call_id" not in action.state_updates


@pytest.mark.asyncio
async def test_completed_booking_result_replay_is_idempotent():
    booking = BookingData.model_validate(
        {
            "booking_id": "booking-001",
            "booking_status": "CONFIRMED",
            "completed_booking_call_id": "booking-call",
        }
    )
    state = AgentState(
        session_id="session-001",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-replay",
            tool_result=ToolResult(
                tool_name=ToolName.CREATE_BOOKING,
                call_id="booking-call",
                status=ToolStatus.SUCCESS,
                data={"booking_id": "booking-001", "status": "CONFIRMED"},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert action.tool_call is None
    assert "trước đó" in (action.message or "")


@pytest.mark.asyncio
async def test_completed_booking_can_be_confirmed_and_cancelled():
    data = BookingData.model_validate(
        {"booking_id": "booking-001", "booking_status": "CONFIRMED"}
    )
    state = booking_state(
        step=BookingStep.CONFIRM_CANCEL,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )
    workflow = RideBookingWorkflow()

    cancel_call = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-confirm-cancel",
            transcript="Đúng",
        ),
        state,
    )
    assert cancel_call.action_type is ActionType.CALL_TOOL
    assert cancel_call.tool_call is not None
    assert cancel_call.tool_call.tool_name is ToolName.CANCEL_BOOKING
    assert cancel_call.tool_call.params["booking_id"] == "booking-001"
    assert cancel_call.tool_call.params["idempotency_key"]

    completed = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-cancel-result",
            tool_result=ToolResult(
                tool_name=ToolName.CANCEL_BOOKING,
                call_id=cancel_call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={"booking_id": "booking-001", "status": "CANCELLED"},
            ),
        ),
        apply_action(state, cancel_call),
    )

    assert completed.action_type is ActionType.RESPOND
    updated = BookingData.model_validate(
        completed.state_updates["collected_data"]["booking"]
    )
    assert updated.booking_status == "CANCELLED"
    assert updated.completed_cancellation_call_id == cancel_call.tool_call.call_id


@pytest.mark.asyncio
async def test_vehicle_correction_invalidates_fare_and_estimates_again():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "vehicle_type": "CAR_4",
            "fare_estimate_id": "fare-old",
            "estimated_fare_amount": 75000,
            "estimated_currency": "VND",
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
            session_id=state.session_id,
            turn_id="turn-change-vehicle",
            transcript="Đổi xe sang xe máy",
        ),
        state,
    )
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.ESTIMATE_FARE
    assert action.tool_call.params["vehicle_type"] == "MOTORBIKE"
    assert updated.vehicle_type == VehicleType.MOTORBIKE.value
    assert updated.fare_estimate_id is None
    assert updated.estimated_fare_amount is None
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_count"),
    [
        ("Tôi đi 2 người", 2),
        ("Tôi đi 3 người, chọn phương tiện phù hợp", 3),
        ("Có 6 hành khách", 6),
    ],
)
async def test_passenger_needs_request_backend_vehicle_options(
    message,
    expected_count,
):
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
        }
    )
    state = booking_state(step=BookingStep.COLLECT_VEHICLE, data=data)

    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-passengers",
            transcript=message,
        ),
        state,
    )
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.GET_VEHICLE_OPTIONS
    assert action.tool_call.params["passenger_count"] == expected_count
    assert updated.passenger_count == expected_count
    assert updated.vehicle_type is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_updates"),
    [
        ("à 3 người", {"passenger_count": 3}),
        ("thực ra có 2 vali", {"luggage_count": 2}),
        ("tôi muốn xe tiết kiệm", {"vehicle_preference": "economical"}),
    ],
)
async def test_late_vehicle_needs_update_replans_instead_of_using_current_prompt(
    message,
    expected_updates,
):
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "passenger_count": 5,
            "luggage_count": 1,
            "vehicle_preference": "comfortable",
            "vehicle_type": "CAR_7",
            "selected_vehicle_option_id": "car-7",
            "vehicle_display_name": "Ô tô 7 chỗ",
            "fare_estimate_id": "fare-7",
            "estimated_fare_amount": 105000,
            "estimated_currency": "VND",
        }
    )
    state = booking_state(
        step=BookingStep.COLLECT_PHONE,
        data=data,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-late-vehicle-needs",
            transcript=message,
        ),
        state,
    )
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.GET_VEHICLE_OPTIONS
    for field, value in expected_updates.items():
        assert getattr(updated, field) == value
        tool_param = "preference" if field == "vehicle_preference" else field
        assert action.tool_call.params[tool_param] == value
    assert updated.vehicle_type is None
    assert updated.selected_vehicle_option_id is None
    assert updated.vehicle_display_name is None
    assert updated.fare_estimate_id is None
    assert updated.estimated_fare_amount is None
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED
    assert "Số điện thoại chưa hợp lệ" not in (action.message or "")

@pytest.mark.asyncio
async def test_late_explicit_vehicle_change_reprices_instead_of_parsing_phone():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "passenger_count": 4,
            "luggage_count": 2,
            "vehicle_type": "CAR_7",
            "selected_vehicle_option_id": "car-7",
            "vehicle_display_name": "Ô tô 7 chỗ",
            "fare_estimate_id": "fare-7",
            "estimated_fare_amount": 105000,
            "estimated_currency": "VND",
        }
    )
    state = booking_state(step=BookingStep.COLLECT_PHONE, data=data)

    action = await LLMAgent().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-late-vehicle-change",
            transcript="thôi 4 chỗ đi",
        ),
        state,
    )
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.ESTIMATE_FARE
    assert action.tool_call.params["vehicle_type"] == VehicleType.CAR_4
    assert updated.vehicle_type == VehicleType.CAR_4
    assert updated.selected_vehicle_option_id is None
    assert updated.vehicle_display_name is None
    assert updated.fare_estimate_id is None
    assert updated.estimated_fare_amount is None
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED
    assert "Số điện thoại chưa hợp lệ" not in (action.message or "")

    follow_up = await LLMAgent().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-updated-vehicle-fare",
            tool_result=fare_result(action.tool_call.call_id),
        ),
        apply_action(state, action),
    )
    repriced = BookingData.model_validate(
        follow_up.state_updates["collected_data"]["booking"]
    )

    assert follow_up.action_type is ActionType.ASK_USER
    assert follow_up.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    assert "75.000 đồng" in (follow_up.message or "")
    assert repriced.vehicle_type == VehicleType.CAR_4
    assert repriced.estimated_fare_amount == 75000


@pytest.mark.asyncio
async def test_structured_passenger_correction_replans_vehicle_options():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "passenger_count": 5,
            "vehicle_type": "CAR_7",
            "selected_vehicle_option_id": "car-7",
            "fare_estimate_id": "fare-7",
            "estimated_fare_amount": 105000,
            "estimated_currency": "VND",
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
            session_id=state.session_id,
            turn_id="turn-passenger-correction",
            transcript="cập nhật lại số khách",
        ),
        state,
        UnderstandingResult(
            corrections=[
                Correction(
                    field=CorrectionField.PASSENGER_COUNT,
                    value="3",
                )
            ]
        ),
    )
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.GET_VEHICLE_OPTIONS
    assert action.tool_call.params["passenger_count"] == 3
    assert updated.passenger_count == 3
    assert updated.vehicle_type is None
    assert updated.fare_estimate_id is None
    assert updated.correction_field is CorrectionField.PASSENGER_COUNT


@pytest.mark.asyncio
async def test_booking_rejects_invalid_legacy_mobile_prefix():
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "vehicle_type": "CAR_4",
            "passenger_count": 3,
            "fare_estimate_id": "fare-001",
            "estimated_fare_amount": 75000,
            "estimated_currency": "VND",
        }
    )
    state = booking_state(step=BookingStep.COLLECT_PHONE, data=data)

    action = await RideBookingWorkflow().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-invalid-phone",
            transcript="0123456789",
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    assert "hợp lệ" in (action.message or "")
    updated = BookingData.model_validate(
        action.state_updates["collected_data"]["booking"]
    )
    assert updated.phone_number is None


@pytest.mark.asyncio
async def test_valid_address_is_processed_after_previous_clarification_failures():
    data = BookingData.model_validate(
        {"pickup": {"place_id": "p1", "display_name": "VinUniversity"}}
    )
    state = booking_state(step=BookingStep.COLLECT_DESTINATION, data=data).model_copy(
        update={"retry_count": 3}
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-valid-after-retries",
            transcript="Times City",
        ),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert action.tool_call.params == {"query": "Times City"}
    assert action.state_updates["retry_count"] == 0


@pytest.mark.asyncio
async def test_llm_recommendation_is_limited_to_backend_vehicle_options():
    workflow = RideBookingWorkflow(vehicle_recommender=StubVehicleRecommender())
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "passenger_count": 3,
            "luggage_count": 2,
            "vehicle_preference": "comfortable",
        }
    )
    state = booking_state(step=BookingStep.COLLECT_VEHICLE, data=data)
    options_call = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-options",
            transcript="Chọn xe phù hợp giúp tôi",
        ),
        state,
    )
    waiting = apply_action(state, options_call)
    assert options_call.tool_call is not None

    recommendation = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-options-result",
            tool_result=ToolResult(
                tool_name=ToolName.GET_VEHICLE_OPTIONS,
                call_id=options_call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "options": [
                        {
                            "option_id": "car-4",
                            "vehicle_type": "CAR_4",
                            "display_name": "Ô tô 4 chỗ",
                            "capacity": 4,
                            "estimate_id": "fare-4",
                            "fare_amount": 75000,
                            "currency": "VND",
                        },
                        {
                            "option_id": "car-7",
                            "vehicle_type": "CAR_7",
                            "display_name": "Ô tô 7 chỗ",
                            "capacity": 7,
                            "estimate_id": "fare-7",
                            "fare_amount": 105000,
                            "currency": "VND",
                        },
                    ]
                },
            ),
        ),
        waiting,
    )

    assert recommendation.action_type is ActionType.ASK_USER
    assert recommendation.state_updates["current_step"] == BookingStep.SELECT_VEHICLE_OPTION
    assert "Ô tô 7 chỗ" in (recommendation.message or "")
    assert "ưu tiên thoải mái" in (recommendation.message or "")

    accepted = await workflow.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-accept-option",
            transcript="Đúng",
        ),
        apply_action(waiting, recommendation),
    )
    selected = BookingData.model_validate(
        accepted.state_updates["collected_data"]["booking"]
    )
    assert accepted.state_updates["current_step"] == BookingStep.COLLECT_PHONE
    assert selected.vehicle_type == VehicleType.CAR_7.value
    assert selected.fare_estimate_id == "fare-7"
