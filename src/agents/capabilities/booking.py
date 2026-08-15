from hashlib import sha256

from src.agents.capabilities.common import policy_error
from src.agents.contracts.schemas import ActionType, AgentAction, ToolName, ToolResult, WorkflowType
from src.agents.contracts.state import ConfirmationStatus
from src.agents.core.booking.actions import (
    request_cancel_booking_action,
    request_create_booking_action,
    request_fare_estimate_action,
    request_place_action,
    request_vehicle_options_action,
)
from src.agents.core.booking.messages import format_fare, passenger_confirmation, vehicle_label
from src.agents.core.booking.state import (
    BookingData,
    BookingStep,
    apply_booking_result,
    apply_cancellation_result,
    apply_fare_result,
    apply_vehicle_options_result,
    clear_completed_booking,
    clear_fare_estimate,
    clear_vehicle_selection,
    draft_from_completed_booking,
    reduce_place_result,
)
from src.agents.core.booking_types import VehicleType
from src.agents.core.phone_policy import is_valid_mobile_phone, normalize_phone
from src.agents.core.registry import ContinueToolLoop, RegisteredTool, ToolRegistry
from src.agents.core.session import TurnSession
from src.agents.core.tools import definition
from src.agents.tools.builders import (
    CancelBookingTool,
    CreateBookingTool,
    EstimateFareTool,
    GetVehicleOptionsTool,
    SearchPlaceTool,
)
from src.agents.tools.lifecycle import clear_pending_tool_updates, parse_tool_result
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    EstimateFareResult,
    GetVehicleOptionsResult,
    PlaceResolutionStatus,
    SearchPlaceResult,
)


def _persist(session: TurnSession) -> None:
    session.persist("booking")
    if "current_workflow" not in session.updates and session.state.current_workflow is None:
        session.updates["current_workflow"] = WorkflowType.RIDE_BOOKING


def _external(session: TurnSession, action: AgentAction) -> AgentAction:
    return action.model_copy(
        update={"state_updates": {**session.updates, **action.state_updates}},
        deep=True,
    )


def _missing(data: BookingData) -> list[str]:
    fields = {
        "điểm đón": data.pickup,
        "điểm đến": data.destination,
        "loại xe": data.vehicle_type,
        "báo giá": data.fare_estimate_id,
        "số điện thoại": data.phone_number,
    }
    return [label for label, value in fields.items() if not value]


def _has_draft(session: TurnSession) -> bool:
    data = session.booking
    return "booking" in session.state.collected_data and any(
        value is not None
        for value in (
            data.pickup_query,
            data.destination_query,
            data.vehicle_type,
            data.passenger_count,
            data.phone_number,
        )
    )


def _has_completed_booking(data: BookingData) -> bool:
    return bool(data.booking_id or data.booking_status or data.completed_booking_call_id)


def _can_start_rebook(data: BookingData) -> bool:
    return bool(_has_completed_booking(data) and data.pickup and data.destination)


def _update(data: BookingData, arguments: dict) -> tuple[BookingData, str]:
    allowed = {
        "pickup_query", "destination_query", "vehicle_type", "passenger_count",
        "luggage_count", "vehicle_preference", "phone_number",
    }
    values = {key: value for key, value in arguments.items() if key in allowed and value is not None}
    for field in ("pickup_query", "destination_query", "vehicle_preference"):
        if field in values:
            values[field] = str(values[field]).strip()
            if not values[field]:
                return data, f"{field} rỗng; state chưa thay đổi."
    if "vehicle_type" in values:
        try:
            values["vehicle_type"] = VehicleType(values["vehicle_type"]).value
        except ValueError:
            return data, "Loại xe không hợp lệ; state chưa thay đổi."
    for field, minimum in (("passenger_count", 1), ("luggage_count", 0)):
        value = values.get(field)
        if value is not None and (not isinstance(value, int) or not minimum <= value <= 50):
            return data, f"{field} không hợp lệ; state chưa thay đổi."
    if "phone_number" in values:
        if not is_valid_mobile_phone(str(values["phone_number"])):
            return data, "Số điện thoại không hợp lệ; state chưa thay đổi."
        values["phone_number"] = normalize_phone(str(values["phone_number"]))

    if values and _has_completed_booking(data):
        data = clear_completed_booking(data)

    location_changed = any(values.get(key) != getattr(data, key) for key in ("pickup_query", "destination_query") if key in values)
    needs_changed = any(values.get(key) != getattr(data, key) for key in ("passenger_count", "luggage_count", "vehicle_preference") if key in values)
    vehicle_changed = "vehicle_type" in values and values["vehicle_type"] != data.vehicle_type
    data = data.model_copy(update=values, deep=True)
    if "pickup_query" in values:
        data = data.model_copy(
            update={
                "pickup": None,
                "pickup_candidates": [],
                "pickup_resolution": PlaceResolutionStatus.UNRESOLVED,
            },
            deep=True,
        )
    if "destination_query" in values:
        data = data.model_copy(
            update={
                "destination": None,
                "destination_candidates": [],
                "destination_resolution": PlaceResolutionStatus.UNRESOLVED,
            },
            deep=True,
        )
    if location_changed or needs_changed:
        data = clear_vehicle_selection(data)
    if vehicle_changed:
        data = data.model_copy(update={"selected_vehicle_option_id": None, "vehicle_display_name": None}, deep=True)
    if location_changed or needs_changed or vehicle_changed:
        data = clear_fare_estimate(data)
    return data, f"Đã cập nhật: {', '.join(values) if values else 'không có trường mới'}."


def register_booking(registry: ToolRegistry) -> None:
    search_builder = SearchPlaceTool()
    options_builder = GetVehicleOptionsTool()
    fare_builder = EstimateFareTool()
    create_builder = CreateBookingTool()
    cancel_builder = CancelBookingTool()

    def update(session: TurnSession, arguments: dict):
        session.booking, note = _update(session.booking, arguments)
        _persist(session)
        return ContinueToolLoop({"booking_updated": note})

    def start_rebook(session: TurnSession, _arguments: dict):
        if not _can_start_rebook(session.booking):
            return policy_error("Không có chuyến cũ đủ thông tin để đặt lại.")
        session.booking = draft_from_completed_booking(session.booking)
        _persist(session)
        session.updates.update(
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step=None,
            confirmation=ConfirmationStatus.NOT_REQUESTED,
        )
        return ContinueToolLoop({
            "rebook_started": {
                "pickup": session.booking.pickup.model_dump(mode="json") if session.booking.pickup else None,
                "destination": session.booking.destination.model_dump(mode="json") if session.booking.destination else None,
                "passenger_count": session.booking.passenger_count,
                "luggage_count": session.booking.luggage_count,
                "phone_number": "đã có và hợp lệ" if session.booking.phone_number else None,
                "needs_vehicle_options": True,
            }
        })

    def select_place(session: TurnSession, arguments: dict):
        target = arguments.get("target")
        candidates = session.booking.pickup_candidates if target == "pickup" else session.booking.destination_candidates
        index = arguments.get("index")
        if target not in {"pickup", "destination"} or not isinstance(index, int) or not 1 <= index <= len(candidates):
            return policy_error("Lựa chọn địa điểm không hợp lệ.")
        selected = candidates[index - 1]
        session.booking = clear_fare_estimate(session.booking.model_copy(
            update={
                target: selected,
                f"{target}_candidates": [],
                f"{target}_resolution": PlaceResolutionStatus.RESOLVED,
            },
            deep=True,
        ))
        _persist(session)
        return ContinueToolLoop({"place_selected": {"target": target, "place": selected.model_dump(mode="json")}})

    def select_vehicle(session: TurnSession, arguments: dict):
        option = next((item for item in session.booking.vehicle_options if item.option_id == arguments.get("option_id")), None)
        if option is None:
            return policy_error("Mã lựa chọn xe không có trong state.")
        session.booking = session.booking.model_copy(update={
            "vehicle_type": option.vehicle_type,
            "selected_vehicle_option_id": option.option_id,
            "vehicle_display_name": option.display_name,
            "fare_estimate_id": option.estimate_id,
            "estimated_fare_amount": option.fare_amount,
            "estimated_currency": option.currency,
            "estimated_eta_minutes": option.eta_minutes,
        }, deep=True)
        _persist(session)
        return ContinueToolLoop({"vehicle_selected": option.model_dump(mode="json")})

    def search(session: TurnSession, pickup: bool):
        query = session.booking.pickup_query if pickup else session.booking.destination_query
        if not query:
            return policy_error("Bạn chưa cung cấp địa điểm cần tìm.")
        resolved = session.booking.pickup if pickup else session.booking.destination
        candidates = session.booking.pickup_candidates if pickup else session.booking.destination_candidates
        if resolved is not None:
            return ContinueToolLoop({
                "place_already_resolved": {
                    "target": "pickup" if pickup else "destination",
                    "place": resolved.model_dump(mode="json"),
                }
            })
        if candidates:
            return ContinueToolLoop({
                "place_already_has_candidates": {
                    "target": "pickup" if pickup else "destination",
                    "count": len(candidates),
                }
            })
        session.booking = session.booking.model_copy(
            update={"pending_location_target": "pickup" if pickup else "destination"},
            deep=True,
        )
        _persist(session)
        action = request_place_action(
            session.working_state(), session.booking, search_builder,
            query=query,
            operation="pickup" if pickup else "destination",
            waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT if pickup else BookingStep.WAITING_FOR_DESTINATION_RESULT,
        )
        return _external(session, action)

    def vehicle_options(session: TurnSession, _arguments: dict):
        data = session.booking
        if not data.pickup or not data.destination or data.passenger_count is None:
            return policy_error("Cần đủ điểm đón, điểm đến và số hành khách trước khi tìm xe.")
        return _external(session, request_vehicle_options_action(session.working_state(), data, options_builder))

    def estimate(session: TurnSession, _arguments: dict):
        data = session.booking
        if not data.pickup or not data.destination or not data.vehicle_type:
            return policy_error("Cần đủ hai địa điểm và loại xe trước khi báo giá.")
        return _external(session, request_fare_estimate_action(session.working_state(), data, fare_builder))

    def request_confirmation(session: TurnSession, _arguments: dict):
        missing = _missing(session.booking)
        if missing:
            return policy_error(f"Chưa thể xác nhận; còn thiếu: {', '.join(missing)}")
        _persist(session)
        session.updates.update(
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step=BookingStep.CONFIRM.value,
            confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        )
        data = session.booking
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=(f"Bạn xác nhận đặt xe đón tại {data.pickup.display_name} và đến "
                     f"{data.destination.display_name}, loại {vehicle_label(data)}, giá dự kiến "
                     f"{format_fare(data)}{passenger_confirmation(data)}, đúng không?"),
            state_updates=session.updates,
            reason="Deterministic policy produced the booking confirmation summary.",
        )

    def confirm(session: TurnSession, _arguments: dict):
        state = session.working_state()
        if state.confirmation is not ConfirmationStatus.AWAITING_CONFIRMATION or state.current_step != BookingStep.CONFIRM.value:
            return policy_error("Chưa có bản tóm tắt đặt xe đang chờ xác nhận.")
        missing = _missing(session.booking)
        if missing:
            return policy_error(f"Thông tin đặt xe còn thiếu: {', '.join(missing)}.")
        key = sha256(f"{state.session_id}:create:{session.booking.fare_estimate_id}:{session.booking.phone_number}".encode()).hexdigest()
        return _external(session, request_create_booking_action(state, session.booking, create_builder, idempotency_key=key))

    def request_cancel(session: TurnSession, _arguments: dict):
        if session.booking.booking_id is None:
            return policy_error("Chưa có booking nào để hủy.")
        _persist(session)
        session.updates.update(
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step=BookingStep.CONFIRM_CANCEL.value,
            confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        )
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn xác nhận muốn hủy chuyến đã đặt này, đúng không?",
            state_updates=session.updates,
            reason="Deterministic policy requires confirmation before cancellation.",
        )

    def confirm_cancel(session: TurnSession, _arguments: dict):
        state = session.working_state()
        if state.confirmation is not ConfirmationStatus.AWAITING_CONFIRMATION or state.current_step != BookingStep.CONFIRM_CANCEL.value or session.booking.booking_id is None:
            return policy_error("Chưa có yêu cầu hủy đang chờ xác nhận.")
        key = sha256(f"{state.session_id}:cancel:{session.booking.booking_id}".encode()).hexdigest()
        return _external(session, request_cancel_booking_action(state, session.booking, cancel_builder, idempotency_key=key))

    def request_abandon(session: TurnSession, _arguments: dict):
        if session.state.pending_tool_name is not None:
            return policy_error("Không thể dừng khi backend đang xử lý.")
        if session.booking.booking_id is not None:
            return policy_error("Chuyến đã tạo phải được xác nhận hủy.")
        if not _has_draft(session):
            return policy_error("Không có booking draft đang hoạt động để dừng.")
        _persist(session)
        session.updates.update(
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step="CONFIRM_ABANDON",
            confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        )
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn dừng và xóa yêu cầu đặt xe đang nhập, đúng không?",
            state_updates=session.updates,
            reason="Deterministic policy requires confirmation before discarding a draft.",
        )

    def confirm_abandon(session: TurnSession, _arguments: dict):
        state = session.working_state()
        if (
            state.confirmation is not ConfirmationStatus.AWAITING_CONFIRMATION
            or state.current_step != "CONFIRM_ABANDON"
        ):
            return policy_error("Chưa có yêu cầu dừng booking đang chờ xác nhận.")
        collected = dict(session.state.collected_data)
        collected.pop("booking", None)
        return AgentAction(
            action_type=ActionType.RESPOND,
            message="Được, tôi đã dừng yêu cầu đặt xe này. Khi nào cần bạn cứ nói nhé.",
            state_updates={"current_workflow": None, "current_step": None, "collected_data": collected,
                           "confirmation": ConfirmationStatus.NOT_REQUESTED, "retry_count": 0},
            reason="The user abandoned the unfinished booking.",
        )

    def keep_booking(session: TurnSession, _arguments: dict):
        if session.working_state().current_step != "CONFIRM_ABANDON":
            return policy_error("Không có yêu cầu dừng booking đang chờ xử lý.")
        _persist(session)
        session.updates.update(
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step=None,
            confirmation=ConfirmationStatus.NOT_REQUESTED,
        )
        return ContinueToolLoop({"booking_retained": True})

    def reduce_search(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, SearchPlaceResult)
        target = session.booking.pending_location_target
        if target not in {"pickup", "destination"}:
            return policy_error("Kết quả địa điểm không có target tương ứng trong typed state.")
        pickup = target == "pickup"
        resolution = reduce_place_result(session.booking, payload, pickup=pickup)
        session.booking = clear_fare_estimate(resolution.data)
        session.booking = session.booking.model_copy(
            update={
                "pickup_resolution" if pickup else "destination_resolution": resolution.status,
                "pending_location_target": None,
            },
            deep=True,
        )
        _finish_result(session)
        return ContinueToolLoop({
            "place_result": {
                "target": "pickup" if pickup else "destination",
                "status": resolution.status.value,
                "candidates": [item.model_dump(mode="json") for item in payload.candidates],
                "clarification_hint": payload.clarification_hint,
            }
        })

    def reduce_options(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, GetVehicleOptionsResult)
        session.booking = apply_vehicle_options_result(session.booking, payload)
        _finish_result(session)
        return ContinueToolLoop({"vehicle_options_result": payload.model_dump(mode="json")})

    def reduce_fare(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, EstimateFareResult)
        session.booking = apply_fare_result(session.booking, payload)
        _finish_result(session)
        return ContinueToolLoop({"fare_result": payload.model_dump(mode="json")})

    def reduce_create(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, CreateBookingResult)
        session.booking = apply_booking_result(session.booking, payload, completed_call_id=result.call_id)
        _finish_result(session)
        session.updates.update(current_workflow=None, confirmation=ConfirmationStatus.NOT_REQUESTED)
        eta = f" Xe dự kiến đến sau {payload.eta_minutes} phút." if payload.eta_minutes is not None else ""
        return AgentAction(action_type=ActionType.RESPOND, message=f"Chuyến xe đã được đặt thành công.{eta}",
                           state_updates=session.updates, reason="Backend confirmed booking creation.")

    def reduce_cancel(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, CancelBookingResult)
        if payload.booking_id != session.booking.booking_id:
            return policy_error("Backend trả về mã chuyến không khớp; cần đối soát.")
        session.booking = apply_cancellation_result(session.booking, payload, completed_call_id=result.call_id)
        _finish_result(session)
        session.updates.update(current_workflow=None, confirmation=ConfirmationStatus.NOT_REQUESTED)
        return AgentAction(action_type=ActionType.RESPOND, message="Chuyến xe đã được hủy thành công.",
                           state_updates=session.updates, reason="Backend confirmed booking cancellation.")

    def _finish_result(session: TurnSession) -> None:
        session.updates.update(clear_pending_tool_updates())
        session.updates.update(current_step=None, retry_count=0)
        _persist(session)

    registry.register(RegisteredTool(definition("update_booking"), update))
    registry.register(RegisteredTool(definition("start_rebook"), start_rebook, lambda s: _can_start_rebook(s.booking)))
    registry.register(RegisteredTool(
        definition("search_pickup"),
        lambda s, a: search(s, True),
        lambda s: bool(
            s.booking.pickup_query
            and not s.booking.pickup
            and not s.booking.pickup_candidates
            and s.booking.pickup_resolution is PlaceResolutionStatus.UNRESOLVED
        ),
    ))
    registry.register(RegisteredTool(
        definition("search_destination"),
        lambda s, a: search(s, False),
        lambda s: bool(
            s.booking.destination_query
            and not s.booking.destination
            and not s.booking.destination_candidates
            and s.booking.destination_resolution is PlaceResolutionStatus.UNRESOLVED
        ),
    ))
    registry.register(RegisteredTool(definition("select_place"), select_place, lambda s: bool(s.booking.pickup_candidates or s.booking.destination_candidates)))
    registry.register(RegisteredTool(definition("request_vehicle_options"), vehicle_options, lambda s: bool(s.booking.pickup and s.booking.destination and s.booking.passenger_count)))
    registry.register(RegisteredTool(definition("select_vehicle"), select_vehicle, lambda s: bool(s.booking.vehicle_options)))
    registry.register(RegisteredTool(definition("estimate_fare"), estimate, lambda s: bool(s.booking.pickup and s.booking.destination and s.booking.vehicle_type and not s.booking.fare_estimate_id)))
    registry.register(RegisteredTool(definition("request_booking_confirmation"), request_confirmation, lambda s: not _missing(s.booking)))
    registry.register(RegisteredTool(definition("confirm_booking"), confirm, lambda s: s.working_state().confirmation is ConfirmationStatus.AWAITING_CONFIRMATION and s.working_state().current_step == BookingStep.CONFIRM.value))
    registry.register(RegisteredTool(definition("request_cancellation_confirmation"), request_cancel, lambda s: s.booking.booking_id is not None))
    registry.register(RegisteredTool(definition("confirm_cancellation"), confirm_cancel, lambda s: s.working_state().confirmation is ConfirmationStatus.AWAITING_CONFIRMATION and s.working_state().current_step == BookingStep.CONFIRM_CANCEL.value))
    registry.register(RegisteredTool(
        definition("request_abandon_confirmation"),
        request_abandon,
        lambda s: s.booking.booking_id is None
        and _has_draft(s)
        and s.working_state().current_step != "CONFIRM_ABANDON",
    ))
    registry.register(RegisteredTool(
        definition("confirm_abandon_booking"),
        confirm_abandon,
        lambda s: s.working_state().confirmation is ConfirmationStatus.AWAITING_CONFIRMATION
        and s.working_state().current_step == "CONFIRM_ABANDON",
    ))
    registry.register(RegisteredTool(
        definition("keep_booking"),
        keep_booking,
        lambda s: s.working_state().current_step == "CONFIRM_ABANDON",
    ))
    registry.register_reducer(ToolName.SEARCH_PLACE, reduce_search)
    registry.register_reducer(ToolName.GET_VEHICLE_OPTIONS, reduce_options)
    registry.register_reducer(ToolName.ESTIMATE_FARE, reduce_fare)
    registry.register_reducer(ToolName.CREATE_BOOKING, reduce_create)
    registry.register_reducer(ToolName.CANCEL_BOOKING, reduce_cancel)
