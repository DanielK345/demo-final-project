from hashlib import sha256

from pydantic import ValidationError

from src.agents.contracts.schemas import ActionType, AgentAction, AgentInput, ToolName, ToolStatus, WorkflowType
from src.agents.contracts.state import AgentState, ConfirmationStatus
from src.agents.core.booking.actions import (
    request_cancel_booking_action,
    request_create_booking_action,
    request_fare_estimate_action,
    request_place_action,
    request_vehicle_options_action,
)
from src.agents.core.booking.messages import (
    format_fare,
    passenger_confirmation,
    vehicle_label,
)
from src.agents.core.booking.state import (
    BookingData,
    BookingStep,
    PlaceResolutionStatus,
    apply_booking_result,
    apply_cancellation_result,
    apply_fare_result,
    apply_vehicle_options_result,
    clear_fare_estimate,
    clear_vehicle_selection,
    reduce_place_result,
)
from src.agents.core.booking_types import VehicleType
from src.agents.core.phone_policy import is_valid_mobile_phone, normalize_phone
from src.agents.core.policy import AgentPolicy
from src.agents.legacy.location_policy import is_ambiguous_location_text
from src.agents.legacy.understanding.models import (
    BookingSelectionTarget,
    ConfirmationIntent,
    CorrectionField,
    UnderstandingResult,
)
from src.agents.legacy.vehicle_recommendation import build_vehicle_recommender
from src.agents.legacy.workflows.base import BaseWorkflow
from src.agents.legacy.workflows.booking.messages import (
    format_option_fare,
    recommendation_reason_text,
)
from src.agents.legacy.workflows.booking.policy import BookingToolFailureKind, plan_booking_tool_failure
from src.agents.legacy.workflows.handoff import HandoffWorkflow
from src.agents.tools.builders import (
    CancelBookingTool,
    CreateBookingTool,
    EstimateFareTool,
    GetVehicleOptionsTool,
    SearchPlaceTool,
)
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    clear_pending_tool_updates,
    correlate_tool_result,
    parse_tool_result,
)
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    EstimateFareResult,
    GetVehicleOptionsResult,
    SearchPlaceResult,
    VehicleOption,
)


class RideBookingWorkflow(BaseWorkflow):
    """Structured booking turn in; validated AgentAction out; no raw-text parsing."""

    workflow_type = WorkflowType.RIDE_BOOKING
    data_key = "booking"
    instructions = "Collect a ride draft, use only backend facts, and require explicit confirmation."
    tool_names = (
        ToolName.SEARCH_PLACE,
        ToolName.GET_VEHICLE_OPTIONS,
        ToolName.ESTIMATE_FARE,
        ToolName.CREATE_BOOKING,
        ToolName.CANCEL_BOOKING,
    )

    def __init__(
        self,
        search_place_tool=None,
        estimate_fare_tool=None,
        get_vehicle_options_tool=None,
        create_booking_tool=None,
        cancel_booking_tool=None,
        policy=None,
        vehicle_recommender=None,
    ):
        self.search_place_tool = search_place_tool or SearchPlaceTool()
        self.estimate_fare_tool = estimate_fare_tool or EstimateFareTool()
        self.get_vehicle_options_tool = get_vehicle_options_tool or GetVehicleOptionsTool()
        self.create_booking_tool = create_booking_tool or CreateBookingTool()
        self.cancel_booking_tool = cancel_booking_tool or CancelBookingTool()
        self.policy = policy or AgentPolicy()
        self.vehicle_recommender = vehicle_recommender or build_vehicle_recommender()

    async def handle(
        self, agent_input: AgentInput, state: AgentState, understanding: UnderstandingResult | None = None
    ) -> AgentAction:
        if agent_input.session_id != state.session_id:
            raise ValueError("agent input and state must belong to the same session")
        try:
            data = self._load(state)
        except ValidationError:
            return await self._handoff(agent_input, state, "Invalid booking state")
        if agent_input.tool_result is not None:
            return await self._tool_result(agent_input, state, data)
        step = self._step(state)
        if step is BookingStep.CONFIRM_CANCEL:
            return self._cancel(state, data, understanding)
        if step in {BookingStep.WAITING_FOR_PICKUP_RESULT, BookingStep.WAITING_FOR_DESTINATION_RESULT}:
            pickup = step is BookingStep.WAITING_FOR_PICKUP_RESULT
            query = (
                None
                if understanding is None
                else (understanding.pickup_query if pickup else understanding.destination_query)
            )
            if query:
                data = self._set_query(data, pickup, query)
                return self._place_call(state, data, pickup)
        if state.pending_tool_name is not None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả xử lý. Bạn vui lòng đợi một chút.",
                reason="Waiting for backend tool result.",
            )
        if understanding is None:
            return self._advance(state, data)
        if understanding.correction_requested and not understanding.corrections:
            return self._ask_correction(state, data)
        data, changed = self._merge(data, understanding)
        data, selected = self._selection(data, understanding)
        changed |= selected
        if (
            step is BookingStep.COLLECT_PHONE
            and agent_input.transcript.strip()
            and understanding.phone_number is None
            and not changed
        ):
            return self._retry(
                state,
                data,
                BookingStep.COLLECT_PHONE,
                "Số điện thoại chưa hợp lệ. Bạn vui lòng đọc lại.",
            )
        if step is BookingStep.CONFIRM:
            if understanding.confirmation is ConfirmationIntent.REJECT and not changed:
                return self._ask_correction(state, data)
            if understanding.confirmation is ConfirmationIntent.CONFIRM and not changed:
                return self._create(state, data)
            if not changed:
                return self._retry(
                    state,
                    data,
                    BookingStep.CONFIRM,
                    "Bạn vui lòng xác nhận đồng ý hoặc nói thông tin cần sửa.",
                    ConfirmationStatus.AWAITING_CONFIRMATION,
                )
        return self._advance(state, data)

    def _merge(self, data: BookingData, turn: UnderstandingResult) -> tuple[BookingData, bool]:
        d, changed = data.model_copy(deep=True), False
        for correction in turn.corrections:
            field, value = correction.field, correction.value
            if field is CorrectionField.PICKUP:
                d = self._set_query(d, True, value) if value else self._clear_place(d, True)
            elif field is CorrectionField.DESTINATION:
                d = self._set_query(d, False, value) if value else self._clear_place(d, False)
            elif field is CorrectionField.PHONE_NUMBER:
                candidate = turn.phone_number or value
                d.phone_number = normalize_phone(candidate) if candidate and is_valid_mobile_phone(candidate) else None
            elif field is CorrectionField.VEHICLE_TYPE:
                d = clear_vehicle_selection(clear_fare_estimate(d))
                try:
                    d.vehicle_type = turn.vehicle_type or (VehicleType(value) if value else None)
                except ValueError:
                    d.vehicle_type = None
            elif field is CorrectionField.PASSENGER_COUNT:
                d = clear_vehicle_selection(clear_fare_estimate(d))
                d.passenger_count = turn.passenger_count or (int(value) if value and value.isdigit() else None)
            changed = True
        if turn.pickup_query:
            changed |= turn.pickup_query.strip(" .,;") != d.pickup_query or d.pickup is None
            d = self._set_query(d, True, turn.pickup_query)
        if turn.destination_query:
            changed |= turn.destination_query.strip(" .,;") != d.destination_query or d.destination is None
            d = self._set_query(d, False, turn.destination_query)
        needs_changed = any(
            v is not None and v != old
            for v, old in (
                (turn.passenger_count, d.passenger_count),
                (turn.luggage_count, d.luggage_count),
                (turn.vehicle_preference, d.vehicle_preference),
            )
        )
        if needs_changed:
            d = clear_vehicle_selection(clear_fare_estimate(d))
            changed = True
        if turn.passenger_count is not None:
            d.passenger_count = turn.passenger_count
        if turn.luggage_count is not None:
            d.luggage_count = turn.luggage_count
        if turn.vehicle_preference is not None:
            d.vehicle_preference = turn.vehicle_preference
        if turn.vehicle_type is not None and turn.vehicle_type != d.vehicle_type:
            d = clear_vehicle_selection(clear_fare_estimate(d))
            d.vehicle_type = turn.vehicle_type
            changed = True
        if (
            turn.phone_number
            and is_valid_mobile_phone(turn.phone_number)
            and normalize_phone(turn.phone_number) != d.phone_number
        ):
            d.phone_number = normalize_phone(turn.phone_number)
            changed = True
        d.correction_field = None
        d.correction_return_step = None
        return d, changed

    def _selection(self, data: BookingData, turn: UnderstandingResult) -> tuple[BookingData, bool]:
        selection = turn.selection
        if selection and selection.target in {BookingSelectionTarget.PICKUP, BookingSelectionTarget.DESTINATION}:
            pickup = selection.target is BookingSelectionTarget.PICKUP
            candidates = data.pickup_candidates if pickup else data.destination_candidates
            if 1 <= selection.index <= len(candidates):
                d = data.model_copy(deep=True)
                if pickup:
                    d.pickup, d.pickup_candidates = candidates[selection.index - 1], []
                else:
                    d.destination, d.destination_candidates = candidates[selection.index - 1], []
                return d, True
        option = None
        if (
            selection
            and selection.target is BookingSelectionTarget.VEHICLE
            and 1 <= selection.index <= len(data.vehicle_options)
        ):
            option = data.vehicle_options[selection.index - 1]
        elif turn.confirmation is ConfirmationIntent.CONFIRM and data.recommended_vehicle_option_id:
            option = next((x for x in data.vehicle_options if x.option_id == data.recommended_vehicle_option_id), None)
        elif turn.vehicle_type and data.vehicle_options:
            matches = [x for x in data.vehicle_options if x.vehicle_type == turn.vehicle_type.value]
            option = matches[0] if len(matches) == 1 else None
        return (self._use_option(data, option), True) if option else (data, False)

    def _advance(self, state: AgentState, data: BookingData, clear=False) -> AgentAction:
        if data.pickup_candidates:
            return self._candidate_ask(state, data, True, clear)
        if data.pickup is None:
            return (
                self._place_call(state, data, True)
                if data.pickup_query
                else self._ask(
                    state, data, BookingStep.COLLECT_PICKUP, "Bạn muốn đón ở đâu?", "Pickup is missing.", clear=clear
                )
            )
        if data.destination_candidates:
            return self._candidate_ask(state, data, False, clear)
        if data.destination is None:
            return (
                self._place_call(state, data, False)
                if data.destination_query
                else self._ask(
                    state,
                    data,
                    BookingStep.COLLECT_DESTINATION,
                    "Bạn muốn đi đến đâu?",
                    "Destination is missing.",
                    clear=clear,
                )
            )
        if data.pickup.place_id == data.destination.place_id:
            data = self._clear_place(data, False)
            return self._ask(
                state,
                data,
                BookingStep.COLLECT_DESTINATION,
                "Điểm đến phải khác điểm đón. Bạn muốn đi đến đâu?",
                "Route endpoints must differ.",
                clear=clear,
            )
        if data.vehicle_options:
            return self._options_ask(state, data, clear)
        if data.vehicle_type is None:
            if data.passenger_count is not None:
                return request_vehicle_options_action(state, data, self.get_vehicle_options_tool)
            return self._ask(
                state,
                data,
                BookingStep.COLLECT_VEHICLE,
                "Bạn đi bao nhiêu người, có bao nhiêu hành lý và ưu tiên xe như thế nào?",
                "Vehicle needs are missing.",
                clear=clear,
            )
        if data.fare_estimate_id is None:
            return request_fare_estimate_action(state, data, self.estimate_fare_tool)
        if data.phone_number is None:
            return self._ask(
                state,
                data,
                BookingStep.COLLECT_PHONE,
                f"Giá dự kiến là {format_fare(data)}. Bạn vui lòng cung cấp số điện thoại đặt xe.",
                "Phone is missing.",
                clear=clear,
            )
        return self._confirm_ask(state, data, clear)

    async def _tool_result(self, inp: AgentInput, state: AgentState, data: BookingData) -> AgentAction:
        result = inp.tool_result
        assert result is not None
        try:
            correlate_tool_result(result, state)
        except ToolLifecycleError as exc:
            return (
                self._reconcile(str(exc))
                if state.pending_tool_name in {ToolName.CREATE_BOOKING, ToolName.CANCEL_BOOKING}
                else await self._handoff(inp, state, str(exc))
            )
        if result.status is ToolStatus.ERROR:
            return await self._tool_failure(inp, state, data)
        try:
            payload = parse_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(inp, state, str(exc))
        step = self._step(state)
        if step in {BookingStep.WAITING_FOR_PICKUP_RESULT, BookingStep.WAITING_FOR_DESTINATION_RESULT} and isinstance(
            payload, SearchPlaceResult
        ):
            pickup = step is BookingStep.WAITING_FOR_PICKUP_RESULT
            resolved = reduce_place_result(data, payload, pickup=pickup)
            if resolved.status is PlaceResolutionStatus.NOT_FOUND:
                return self._retry(
                    state,
                    resolved.data,
                    BookingStep.COLLECT_PICKUP if pickup else BookingStep.COLLECT_DESTINATION,
                    f"Tôi chưa tìm thấy {'điểm đón' if pickup else 'điểm đến'}. Bạn vui lòng nói địa chỉ cụ thể hơn.",
                    clear=True,
                )
            return self._advance(state, resolved.data, True)
        if step is BookingStep.WAITING_FOR_FARE_ESTIMATE and isinstance(payload, EstimateFareResult):
            return self._advance(state, apply_fare_result(data, payload), True)
        if step is BookingStep.WAITING_FOR_VEHICLE_OPTIONS and isinstance(payload, GetVehicleOptionsResult):
            return await self._vehicle_result(state, data, payload)
        if step is BookingStep.WAITING_FOR_BOOKING_RESULT and isinstance(payload, CreateBookingResult):
            return self._booking_done(state, data, payload)
        if step is BookingStep.WAITING_FOR_CANCELLATION_RESULT and isinstance(payload, CancelBookingResult):
            return self._cancel_done(state, data, payload)
        return await self._handoff(inp, state, "Tool result is invalid for booking state")

    async def _tool_failure(self, inp, state, data):
        plan = plan_booking_tool_failure(inp.tool_result, state, data, self.policy)
        if plan.kind in {BookingToolFailureKind.RETRY_PICKUP, BookingToolFailureKind.RETRY_DESTINATION}:
            action = self._place_call(state, data, plan.kind is BookingToolFailureKind.RETRY_PICKUP)
        elif plan.kind is BookingToolFailureKind.RETRY_VEHICLE_OPTIONS:
            action = request_vehicle_options_action(state, data, self.get_vehicle_options_tool)
        elif plan.kind is BookingToolFailureKind.RETRY_FARE:
            action = request_fare_estimate_action(state, data, self.estimate_fare_tool)
        elif plan.kind is BookingToolFailureKind.RECONCILE:
            return self._reconcile(plan.reason)
        elif plan.kind is BookingToolFailureKind.CONFIRM_BOOKING_RETRY:
            return self._ask(
                state,
                data,
                BookingStep.CONFIRM,
                "Yêu cầu đặt xe chưa thành công. Bạn có muốn thử xác nhận lại không?",
                plan.reason,
                ConfirmationStatus.AWAITING_CONFIRMATION,
                True,
            )
        elif plan.kind is BookingToolFailureKind.CONFIRM_CANCELLATION_RETRY:
            return self._ask(
                state,
                data,
                BookingStep.CONFIRM_CANCEL,
                "Hủy chuyến chưa thành công. Bạn có muốn thử lại không?",
                plan.reason,
                ConfirmationStatus.AWAITING_CONFIRMATION,
                True,
            )
        else:
            return await self._handoff(inp, state, plan.reason)
        action.state_updates["retry_count"] = plan.retry_count
        return action

    async def _vehicle_result(self, state, data, payload):
        data = apply_vehicle_options_result(data, payload)
        if not data.vehicle_options:
            return self._ask(
                state,
                data,
                BookingStep.COLLECT_VEHICLE,
                "Hiện chưa có xe phù hợp. Bạn muốn điều chỉnh nhu cầu không?",
                "No vehicle option.",
                clear=True,
            )
        rec = await self.vehicle_recommender.recommend(
            session_id=state.session_id,
            passenger_count=data.passenger_count,
            luggage_count=data.luggage_count,
            preference=data.vehicle_preference,
            options=data.vehicle_options,
        )
        data.recommended_vehicle_option_id = (
            rec.option_id if rec.option_id in {x.option_id for x in data.vehicle_options} else None
        )
        return self._options_ask(
            state,
            data,
            True,
            recommendation_reason_text(rec.reason),
        )

    def _place_call(self, state, data, pickup):
        query = data.pickup_query if pickup else data.destination_query
        assert query
        label = "điểm đón" if pickup else "điểm đến"
        if is_ambiguous_location_text(query):
            return self._ask(
                state,
                data,
                BookingStep.COLLECT_PICKUP if pickup else BookingStep.COLLECT_DESTINATION,
                f"Bạn vui lòng cung cấp địa chỉ {label} cụ thể.",
                "Ambiguous location.",
            )
        return request_place_action(
            state,
            data,
            self.search_place_tool,
            query=query,
            operation="pickup" if pickup else "destination",
            waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT
            if pickup
            else BookingStep.WAITING_FOR_DESTINATION_RESULT,
        )

    def _candidate_ask(self, state, data, pickup, clear):
        items = data.pickup_candidates if pickup else data.destination_candidates
        choices = "; ".join(f"{i}. {x.display_name}" for i, x in enumerate(items[:3], 1))
        return self._ask(
            state,
            data,
            BookingStep.SELECT_PICKUP_CANDIDATE if pickup else BookingStep.SELECT_DESTINATION_CANDIDATE,
            f"Tôi tìm thấy nhiều {'điểm đón' if pickup else 'điểm đến'}: {choices}. Bạn chọn số mấy?",
            "Place selection required.",
            clear=clear,
        )

    def _options_ask(self, state, data, clear, recommendation_reason=""):
        choices = "; ".join(
            f"{i}. {x.display_name}, {format_option_fare(x)}" for i, x in enumerate(data.vehicle_options, 1)
        )
        recommended = next((x for x in data.vehicle_options if x.option_id == data.recommended_vehicle_option_id), None)
        text = f" Tôi đề xuất {recommended.display_name}{recommendation_reason}." if recommended else ""
        return self._ask(
            state,
            data,
            BookingStep.SELECT_VEHICLE_OPTION,
            f"Hiện có: {choices}.{text} Bạn chọn phương án nào?",
            "Vehicle selection required.",
            clear=clear,
        )

    @staticmethod
    def _use_option(data, option: VehicleOption):
        return data.model_copy(
            update={
                "vehicle_type": option.vehicle_type,
                "selected_vehicle_option_id": option.option_id,
                "vehicle_display_name": option.display_name,
                "fare_estimate_id": option.estimate_id,
                "estimated_fare_amount": option.fare_amount,
                "estimated_currency": option.currency,
                "estimated_eta_minutes": option.eta_minutes,
                "vehicle_options": [],
                "recommended_vehicle_option_id": None,
            },
            deep=True,
        )

    def _confirm_ask(self, state, data, clear):
        msg = f"Bạn xác nhận đặt xe đón tại {data.pickup.display_name} và đến {data.destination.display_name}, loại {vehicle_label(data)}, giá dự kiến {format_fare(data)}{passenger_confirmation(data)}, đúng không?"
        return self._ask(
            state,
            data,
            BookingStep.CONFIRM,
            msg,
            "Explicit confirmation required.",
            ConfirmationStatus.AWAITING_CONFIRMATION,
            clear,
        )

    def _create(self, state, data):
        if not all((data.pickup, data.destination, data.vehicle_type, data.fare_estimate_id, data.phone_number)):
            return AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển bạn tới tổng đài viên để kiểm tra thông tin.",
                state_updates={"current_workflow": WorkflowType.HUMAN_HANDOFF, "current_step": "HANDOFF_REQUIRED"},
                reason="Incomplete confirmation state.",
            )
        key = self._key(state.session_id, "create", data.fare_estimate_id, data.phone_number)
        return request_create_booking_action(state, data, self.create_booking_tool, idempotency_key=key)

    def _cancel(self, state, data, turn):
        decision = turn.confirmation if turn else ConfirmationIntent.UNCLEAR
        if decision is ConfirmationIntent.REJECT:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Tôi sẽ giữ nguyên chuyến xe đã đặt.",
                state_updates={
                    "current_workflow": None,
                    "current_step": None,
                    "confirmation": ConfirmationStatus.NOT_REQUESTED,
                    "retry_count": 0,
                },
                reason="Cancellation rejected.",
            )
        if decision is not ConfirmationIntent.CONFIRM:
            return self._retry(
                state,
                data,
                BookingStep.CONFIRM_CANCEL,
                "Bạn vui lòng xác nhận có muốn hủy chuyến đã đặt không.",
                ConfirmationStatus.AWAITING_CONFIRMATION,
            )
        return request_cancel_booking_action(
            state,
            data,
            self.cancel_booking_tool,
            idempotency_key=self._key(state.session_id, "cancel", data.booking_id),
        )

    def _booking_done(self, state, data, result):
        data = apply_booking_result(data, result, completed_call_id=state.pending_tool_call_id)
        eta = f" Xe dự kiến đến sau {result.eta_minutes} phút." if result.eta_minutes is not None else ""
        return self._done(state, data, f"Chuyến xe đã được đặt thành công.{eta}", "Booking completed.")

    def _cancel_done(self, state, data, result):
        if result.booking_id != data.booking_id:
            return self._reconcile("Cancellation returned another booking ID")
        return self._done(
            state,
            apply_cancellation_result(data, result, completed_call_id=state.pending_tool_call_id),
            "Chuyến xe đã được hủy thành công.",
            "Cancellation completed.",
        )

    def _done(self, state, data, message, reason):
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=message,
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store(state, data),
                "retry_count": 0,
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                **clear_pending_tool_updates(),
            },
            reason=reason,
        )

    def _ask_correction(self, state, data):
        return self._ask(
            state,
            data,
            BookingStep.SELECT_CORRECTION_FIELD,
            "Bạn muốn sửa điểm đón, điểm đến, số người, loại xe hay số điện thoại?",
            "Correction field required.",
            ConfirmationStatus.REJECTED,
        )

    def _ask(self, state, data, step, message, reason, confirmation=ConfirmationStatus.NOT_REQUESTED, clear=False):
        updates = {
            "current_workflow": self.workflow_type,
            "current_step": step.value,
            "collected_data": self._store(state, data),
            "confirmation": confirmation,
            "retry_count": 0,
        }
        if clear:
            updates.update(clear_pending_tool_updates())
        return AgentAction(action_type=ActionType.ASK_USER, message=message, state_updates=updates, reason=reason)

    def _retry(self, state, data, step, message, confirmation=ConfirmationStatus.NOT_REQUESTED, clear=False):
        if state.retry_count + 1 >= self.policy.max_retry_count:
            updates = {
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "HANDOFF_REQUIRED",
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
            }
            if clear:
                updates.update(clear_pending_tool_updates())
            return AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển bạn tới tổng đài viên để hỗ trợ tiếp.",
                state_updates=updates,
                reason="Retry limit reached.",
            )
        action = self._ask(state, data, step, message, "Clearer booking information required.", confirmation, clear)
        action.state_updates["retry_count"] = state.retry_count + 1
        return action

    @staticmethod
    def _set_query(data, pickup, query):
        d = RideBookingWorkflow._clear_place(data, pickup)
        query = query.strip(" .,;")
        if pickup:
            d.pickup_query = query
        else:
            d.destination_query = query
        return d

    @staticmethod
    def _clear_place(data, pickup):
        updates = (
            {"pickup_query": None, "pickup": None, "pickup_candidates": []}
            if pickup
            else {"destination_query": None, "destination": None, "destination_candidates": []}
        )
        return clear_fare_estimate(data.model_copy(update=updates, deep=True))

    async def _handoff(self, inp, state, reason):
        action = await HandoffWorkflow().handle(inp, state)
        action.reason = reason
        return action

    def _load(self, state):
        return BookingData.model_validate(state.collected_data.get(self.data_key, {}))

    def _store(self, state, data):
        return {**state.collected_data, self.data_key: data.model_dump(mode="json")}

    @staticmethod
    def _step(state):
        try:
            return BookingStep(state.current_step) if state.current_step else None
        except ValueError:
            return None

    @staticmethod
    def _key(session, operation, *values):
        return f"agent-{operation}-{sha256('|'.join((session, operation, *values)).encode()).hexdigest()[:24]}"

    @staticmethod
    def _reconcile(reason):
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message="Tôi cần kiểm tra trạng thái giao dịch và sẽ chuyển bạn tới tổng đài viên.",
            state_updates={"current_workflow": WorkflowType.HUMAN_HANDOFF, "current_step": "RECONCILIATION_REQUIRED"},
            reason=reason,
        )
