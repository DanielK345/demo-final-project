import re
from typing import Any

from pydantic import ValidationError

from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.tools.booking import CreateBookingTool
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    clear_pending_tool_updates,
    correlate_tool_result,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.maps import SearchPlaceTool
from src.agents.tools.schemas import CreateBookingResult, SearchPlaceResult
from src.agents.understanding.models import (
    ConfirmationIntent,
    CorrectionField,
    UnderstandingResult,
)
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking_models import BookingData, BookingLifecycleStatus, BookingStep, VehicleType
from src.agents.workflows.handoff import HandoffWorkflow

_ROUTE_PATTERN = re.compile(
    r"\btừ\s+(?P<pickup>.+?)\s+(?:đến|tới|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_DESTINATION_ONLY = re.compile(
    r"^(?:tôi\s+)?(?:muốn\s+)?(?:đi|tới|đến|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_CONFIRM_TERMS = ("đúng", "đồng ý", "xác nhận", "đặt đi", "đặt giúp")
_REJECT_TERMS = ("không", "chưa", "hủy", "sai rồi")
_PICKUP_CORRECTION = re.compile(
    r"(?:đổi|sửa)\s+(?:điểm\s+)?đón(?:\s+thành|\s+là)?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_DESTINATION_CORRECTION = re.compile(
    r"(?:đổi|sửa)\s+(?:điểm\s+)?(?:đến|đích)(?:\s+thành|\s+là)?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_VEHICLE_TERMS: dict[VehicleType, tuple[str, ...]] = {
    VehicleType.FOUR_SEAT: ("4 chỗ", "xe 4", "bốn chỗ", "sedan"),
    VehicleType.SEVEN_SEAT: ("7 chỗ", "xe 7", "bảy chỗ", "suv"),
    VehicleType.PREMIUM: ("hạng sang", "premium", "luxury", "vip"),
}
_VEHICLE_LABELS: dict[VehicleType, str] = {
    VehicleType.FOUR_SEAT: "xe 4 chỗ",
    VehicleType.SEVEN_SEAT: "xe 7 chỗ",
    VehicleType.PREMIUM: "xe hạng sang",
}
_BOOKING_INTRO = (
    "Em chỉ cần điểm đón, điểm đến và loại xe (4 chỗ, 7 chỗ hoặc hạng sang). "
    "Em không hỏi số điện thoại, email hay thông tin riêng tư."
)
_ACCOUNT_PHONE_PLACEHOLDER = "authenticated_account"
_FIELD_MESSAGES: dict[str, str] = {
    "pickup": "Anh/chị muốn đón ở đâu?",
    "destination": "Anh/chị muốn đi đến đâu?",
    "vehicle_type": (
        "Anh/chị muốn đặt loại xe nào: 4 chỗ, 7 chỗ hay hạng sang?"
    ),
}
_FIELD_STEPS: dict[str, BookingStep] = {
    "pickup": BookingStep.COLLECT_PICKUP,
    "destination": BookingStep.COLLECT_DESTINATION,
    "vehicle_type": BookingStep.COLLECT_VEHICLE_TYPE,
}


class RideBookingWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING
    data_key = "booking"

    def __init__(
        self,
        search_place_tool: SearchPlaceTool | None = None,
        create_booking_tool: CreateBookingTool | None = None,
    ) -> None:
        self.search_place_tool = search_place_tool or SearchPlaceTool()
        self.create_booking_tool = create_booking_tool or CreateBookingTool()

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> AgentAction:
        if agent_input.session_id != state.session_id:
            raise ValueError("agent input and state must belong to the same session")

        try:
            data = self._load_data(state)
        except ValidationError:
            return await self._handoff(agent_input, state, "Invalid booking state")

        if agent_input.tool_result is not None:
            return await self._handle_tool_result(agent_input, state, data)

        step = self._step(state)
        transcript = agent_input.transcript.strip()

        correction = self._understood_correction(understanding)
        if correction is None:
            correction = self._extract_correction(transcript)
        if correction is not None:
            field, value = correction
            return self._apply_correction(state, data, field, value)

        if step is BookingStep.COLLECT_PICKUP:
            return self._collect_pickup(state, data, transcript, understanding)
        if step is BookingStep.SELECT_PICKUP_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=True)
        if step is BookingStep.COLLECT_DESTINATION:
            return self._collect_destination(state, data, transcript, understanding)
        if step is BookingStep.SELECT_DESTINATION_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=False)
        if step is BookingStep.COLLECT_VEHICLE_TYPE:
            return self._collect_vehicle_type(state, data, transcript, understanding)
        if step is BookingStep.CONFIRM:
            return self._handle_confirmation(
                state,
                data,
                transcript,
                understanding,
            )
        if step in {
            BookingStep.WAITING_FOR_PICKUP_RESULT,
            BookingStep.WAITING_FOR_DESTINATION_RESULT,
            BookingStep.WAITING_FOR_BOOKING_RESULT,
        }:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả xử lý. Bạn vui lòng đợi một chút.",
                reason="The workflow is waiting for a tool result.",
            )
        if step is BookingStep.COMPLETE:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Chuyến xe đã được đặt thành công.",
                reason="The booking workflow is already complete.",
            )

        return self._start_booking(state, data, transcript, understanding)

    def _start_booking(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        if understanding is not None and understanding.pickup_query:
            data.pickup_query = understanding.pickup_query
            data.destination_query = understanding.destination_query
            if understanding.vehicle_type:
                data.vehicle_type = self._normalize_vehicle_type(understanding.vehicle_type)
            return self._request_place(
                state,
                data,
                query=data.pickup_query,
                operation="pickup",
                waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
            )
        route = _ROUTE_PATTERN.search(transcript)
        if route is not None:
            data.pickup_query = route.group("pickup").strip(" .")
            data.destination_query = route.group("destination").strip(" .")
            parsed_vehicle = self._parse_vehicle_type(transcript)
            if parsed_vehicle is not None:
                data.vehicle_type = parsed_vehicle
            return self._request_place(
                state,
                data,
                query=data.pickup_query,
                operation="pickup",
                waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
            )

        return self._ask_for_missing(
            state,
            data,
            include_intro=True,
            reason="Ride booking requires pickup, destination, and vehicle type.",
        )

    def _missing_field(self, data: BookingData) -> str | None:
        if data.pickup is None:
            return "pickup"
        if data.destination is None:
            return "destination"
        if data.vehicle_type is None:
            return "vehicle_type"
        return None

    def _ask_for_missing(
        self,
        state: AgentState,
        data: BookingData,
        *,
        include_intro: bool = False,
        reason: str | None = None,
        clear_pending: bool = False,
    ) -> AgentAction:
        field = self._missing_field(data)
        if field is None:
            return self._confirmation_action(state, data, clear_pending=clear_pending)
        message = _FIELD_MESSAGES[field]
        if include_intro:
            message = f"{_BOOKING_INTRO} {message}"
        return self._ask(
            state,
            data,
            step=_FIELD_STEPS[field],
            message=message,
            reason=reason or f"The {field.replace('_', ' ')} is missing.",
            clear_pending=clear_pending,
        )

    @staticmethod
    def _parse_destination_only(transcript: str) -> str | None:
        match = _DESTINATION_ONLY.match(transcript.strip())
        if match is None:
            return None
        destination = match.group("destination").strip(" .")
        return destination or None

    def _parse_destination_query(
        self,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> str | None:
        if understanding is not None and understanding.destination_query:
            return understanding.destination_query
        return self._parse_destination_only(transcript)

    def _extract_pickup_query(
        self,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> str | None:
        if self._parse_destination_only(transcript) is not None:
            return None
        if understanding is not None and understanding.pickup_query:
            return understanding.pickup_query
        cleaned = transcript.strip()
        return cleaned or None

    def _collect_pickup(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        destination = self._parse_destination_query(transcript, understanding)
        if destination and data.pickup is None and data.destination is None:
            data.destination_query = destination
            if understanding is not None and understanding.vehicle_type:
                data.vehicle_type = self._normalize_vehicle_type(
                    understanding.vehicle_type
                )
            return self._ask_for_missing(state, data)

        pickup = self._extract_pickup_query(transcript, understanding)
        if understanding is not None and understanding.destination_query:
            data.destination_query = understanding.destination_query
        if understanding is not None and understanding.vehicle_type:
            data.vehicle_type = self._normalize_vehicle_type(understanding.vehicle_type)
        if not pickup:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_PICKUP,
                "Anh/chị vui lòng nói lại điểm đón.",
            )
        data.pickup_query = pickup
        data.pickup = None
        data.pickup_candidates = []
        return self._request_place(
            state,
            data,
            query=pickup,
            operation="pickup",
            waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
        )

    def _collect_destination(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        destination = self._parse_destination_query(transcript, understanding)
        if destination is None:
            destination = transcript.strip() or None
        if not destination:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_DESTINATION,
                "Anh/chị vui lòng nói lại điểm đến.",
            )
        data.destination_query = destination
        data.destination = None
        data.destination_candidates = []
        return self._request_place(
            state,
            data,
            query=destination,
            operation="destination",
            waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
        )

    def _request_place(
        self,
        state: AgentState,
        data: BookingData,
        *,
        query: str,
        operation: str,
        waiting_step: BookingStep,
    ) -> AgentAction:
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.SEARCH_PLACE,
            operation=operation,
            sequence=state.state_version + 1,
        )
        tool_call = self.search_place_tool.build_call(call_id, query=query)
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates={
                "current_workflow": self.workflow_type,
                "collected_data": self._store_data(state, data),
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                **pending_tool_updates(tool_call, waiting_step=waiting_step.value),
            },
            reason=f"The {operation} location must be resolved.",
        )

    async def _handle_tool_result(
        self,
        agent_input: AgentInput,
        state: AgentState,
        data: BookingData,
    ) -> AgentAction:
        result = agent_input.tool_result
        assert result is not None
        try:
            correlate_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))

        if result.status is ToolStatus.ERROR:
            step = self._step(state)
            if step is BookingStep.WAITING_FOR_BOOKING_RESULT:
                return self._fail_booking(state, data, result.error or "Booking failed")
            return await self._handoff(
                agent_input,
                state,
                f"Critical tool error: {result.error}",
            )

        try:
            payload = parse_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))

        step = self._step(state)
        if (
            step is BookingStep.WAITING_FOR_PICKUP_RESULT
            and isinstance(payload, SearchPlaceResult)
        ):
            return self._process_place_result(state, data, payload, pickup=True)
        if (
            step is BookingStep.WAITING_FOR_DESTINATION_RESULT
            and isinstance(payload, SearchPlaceResult)
        ):
            return self._process_place_result(state, data, payload, pickup=False)
        if (
            step is BookingStep.WAITING_FOR_BOOKING_RESULT
            and isinstance(payload, CreateBookingResult)
        ):
            return self._complete_booking(state, data, payload)
        return await self._handoff(
            agent_input,
            state,
            "Tool result is not valid for the current booking step",
        )

    def _process_place_result(
        self,
        state: AgentState,
        data: BookingData,
        result: SearchPlaceResult,
        *,
        pickup: bool,
    ) -> AgentAction:
        candidates = result.candidates
        if not candidates:
            step = (
                BookingStep.COLLECT_PICKUP
                if pickup
                else BookingStep.COLLECT_DESTINATION
            )
            label = "điểm đón" if pickup else "điểm đến"
            if pickup:
                data.pickup = None
                data.pickup_candidates = []
            else:
                data.destination = None
                data.destination_candidates = []
            return self._retry_ask(
                state,
                data,
                step,
                f"Tôi chưa tìm thấy {label}. Bạn vui lòng nói địa chỉ cụ thể hơn.",
                clear_pending=True,
            )

        if len(candidates) > 1:
            if pickup:
                data.pickup_candidates = candidates
                step = BookingStep.SELECT_PICKUP_CANDIDATE
                label = "điểm đón"
            else:
                data.destination_candidates = candidates
                step = BookingStep.SELECT_DESTINATION_CANDIDATE
                label = "điểm đến"
            choices = "; ".join(
                f"{index}. {candidate.display_name}"
                for index, candidate in enumerate(candidates[:3], start=1)
            )
            return self._ask(
                state,
                data,
                step=step,
                message=f"Tôi tìm thấy nhiều {label}: {choices}. Bạn chọn số mấy?",
                reason=f"The {label} is ambiguous.",
                clear_pending=True,
            )

        if pickup:
            data.pickup = candidates[0]
            data.pickup_candidates = []
            if data.destination_query:
                return self._request_place(
                    state,
                    data,
                    query=data.destination_query,
                    operation="destination",
                    waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
                )
            return self._ask_for_missing(state, data, clear_pending=True)

        data.destination = candidates[0]
        data.destination_candidates = []
        return self._after_locations(state, data, clear_pending=True)

    def _select_candidate(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        *,
        pickup: bool,
    ) -> AgentAction:
        candidates = data.pickup_candidates if pickup else data.destination_candidates
        candidate = self._match_candidate(transcript, candidates)
        step = (
            BookingStep.SELECT_PICKUP_CANDIDATE
            if pickup
            else BookingStep.SELECT_DESTINATION_CANDIDATE
        )
        if candidate is None:
            return self._retry_ask(
                state,
                data,
                step,
                "Tôi chưa xác định được lựa chọn. Bạn vui lòng nói số thứ tự.",
            )

        if pickup:
            data.pickup = candidate
            data.pickup_candidates = []
            if data.destination_query:
                return self._request_place(
                    state,
                    data,
                    query=data.destination_query,
                    operation="destination",
                    waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
                )
            return self._ask_for_missing(state, data)

        data.destination = candidate
        data.destination_candidates = []
        return self._after_locations(state, data)

    def _after_locations(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        return self._ask_for_missing(state, data, clear_pending=clear_pending)

    def _collect_vehicle_type(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        vehicle_type = None
        if understanding is not None and understanding.vehicle_type:
            vehicle_type = self._normalize_vehicle_type(understanding.vehicle_type)
        if vehicle_type is None:
            vehicle_type = self._parse_vehicle_type(transcript)
        if vehicle_type is None:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_VEHICLE_TYPE,
                (
                    "Em chưa nhận được loại xe. Anh/chị vui lòng chọn "
                    "4 chỗ, 7 chỗ hoặc hạng sang."
                ),
            )
        data.vehicle_type = vehicle_type
        return self._confirmation_action(state, data)

    def _confirmation_action(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        assert data.pickup is not None
        assert data.destination is not None
        assert data.vehicle_type is not None
        vehicle_label = _VEHICLE_LABELS[data.vehicle_type]
        return self._ask(
            state,
            data,
            step=BookingStep.CONFIRM,
            message=(
                f"Anh/chị xác nhận đặt {vehicle_label} đón tại "
                f"{data.pickup.display_name} và đến {data.destination.display_name}, "
                "đúng không?"
            ),
            reason="Explicit confirmation is required before booking.",
            confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
            clear_pending=clear_pending,
        )

    def _handle_confirmation(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        normalized = transcript.casefold()
        rejected = (
            understanding is not None
            and understanding.confirmation is ConfirmationIntent.REJECT
        ) or any(term in normalized for term in _REJECT_TERMS)
        confirmed = (
            understanding is not None
            and understanding.confirmation is ConfirmationIntent.CONFIRM
        ) or any(term in normalized for term in _CONFIRM_TERMS)
        if rejected:
            return self._ask(
                state,
                data,
                step=BookingStep.CONFIRM,
                message="Anh/chị muốn sửa điểm đón, điểm đến hay loại xe?",
                reason="The user rejected the booking details.",
                confirmation=ConfirmationStatus.REJECTED,
            )
        if not confirmed:
            return self._retry_ask(
                state,
                data,
                BookingStep.CONFIRM,
                "Bạn vui lòng xác nhận đồng ý hoặc nói thông tin cần sửa.",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
            )
        if data.pickup is None or data.destination is None or data.vehicle_type is None:
            return AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển bạn tới tổng đài viên để kiểm tra thông tin.",
                state_updates={
                    "current_workflow": WorkflowType.HUMAN_HANDOFF,
                    "current_step": "HANDOFF_REQUIRED",
                    **clear_pending_tool_updates(),
                },
                reason="Booking confirmation state is incomplete.",
            )

        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.CREATE_BOOKING,
            operation="booking",
            sequence=state.state_version + 1,
        )
        data.lifecycle_status = BookingLifecycleStatus.PENDING
        tool_call = self.create_booking_tool.build_call(
            call_id,
            pickup_place_id=data.pickup.place_id,
            destination_place_id=data.destination.place_id,
            phone_number=_ACCOUNT_PHONE_PLACEHOLDER,
        )
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates={
                "current_workflow": self.workflow_type,
                "collected_data": self._store_data(state, data),
                "confirmation": ConfirmationStatus.CONFIRMED,
                **pending_tool_updates(
                    tool_call,
                    waiting_step=BookingStep.WAITING_FOR_BOOKING_RESULT.value,
                ),
            },
            reason="The user explicitly confirmed the booking.",
        )

    def _complete_booking(
        self,
        state: AgentState,
        data: BookingData,
        result: CreateBookingResult,
    ) -> AgentAction:
        data.booking_id = result.booking_id
        data.booking_status = result.status
        data.lifecycle_status = BookingLifecycleStatus.SUCCESS
        data.eta_minutes = result.eta_minutes
        data.fare_amount = result.fare_amount
        data.currency = result.currency
        details = []
        if result.eta_minutes is not None:
            details.append(f"Xe dự kiến đến sau {result.eta_minutes} phút.")
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=" ".join(["Chuyến xe đã được đặt thành công.", *details]),
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                "retry_count": 0,
                **clear_pending_tool_updates(),
            },
            reason="The booking tool returned a successful result.",
        )

    def _fail_booking(
        self,
        state: AgentState,
        data: BookingData,
        error_message: str,
    ) -> AgentAction:
        data.lifecycle_status = BookingLifecycleStatus.FAILED
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=(
                "Em chưa đặt được xe lúc này. Anh/chị vui lòng thử lại "
                "hoặc liên hệ tổng đài viên."
            ),
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": BookingStep.CONFIRM.value,
                "collected_data": self._store_data(state, data),
                "confirmation": ConfirmationStatus.AWAITING_CONFIRMATION,
                **clear_pending_tool_updates(),
            },
            reason=f"Booking tool failed: {error_message}",
        )

    def _apply_correction(
        self,
        state: AgentState,
        data: BookingData,
        field: str,
        value: str,
    ) -> AgentAction:
        if field == "pickup":
            data.pickup_query = value
            data.pickup = None
            data.pickup_candidates = []
            return self._request_place(
                state,
                data,
                query=value,
                operation="pickup",
                waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
            )
        if field == "vehicle_type":
            vehicle_type = self._parse_vehicle_type(value) or self._normalize_vehicle_type(value)
            if vehicle_type is None:
                return self._retry_ask(
                    state,
                    data,
                    BookingStep.COLLECT_VEHICLE_TYPE,
                    (
                        "Em chưa nhận được loại xe. Anh/chị vui lòng chọn "
                        "4 chỗ, 7 chỗ hoặc hạng sang."
                    ),
                )
            data.vehicle_type = vehicle_type
            return self._after_locations(state, data)
        data.destination_query = value
        data.destination = None
        data.destination_candidates = []
        return self._request_place(
            state,
            data,
            query=value,
            operation="destination",
            waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
        )

    def _ask(
        self,
        state: AgentState,
        data: BookingData,
        *,
        step: BookingStep,
        message: str,
        reason: str,
        confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED,
        clear_pending: bool = False,
    ) -> AgentAction:
        updates: dict[str, Any] = {
            "current_workflow": self.workflow_type,
            "current_step": step.value,
            "collected_data": self._store_data(state, data),
            "confirmation": confirmation,
        }
        if clear_pending:
            updates.update(clear_pending_tool_updates())
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message=message,
            state_updates=updates,
            reason=reason,
        )

    def _retry_ask(
        self,
        state: AgentState,
        data: BookingData,
        step: BookingStep,
        message: str,
        *,
        confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED,
        clear_pending: bool = False,
    ) -> AgentAction:
        action = self._ask(
            state,
            data,
            step=step,
            message=message,
            reason="The user must provide clearer booking information.",
            confirmation=confirmation,
            clear_pending=clear_pending,
        )
        action.state_updates["retry_count"] = state.retry_count + 1
        return action

    async def _handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
        reason: str,
    ) -> AgentAction:
        action = await HandoffWorkflow().handle(agent_input, state)
        action.reason = reason
        return action

    def _load_data(self, state: AgentState) -> BookingData:
        return BookingData.model_validate(state.collected_data.get(self.data_key, {}))

    def _store_data(
        self,
        state: AgentState,
        data: BookingData,
    ) -> dict[str, Any]:
        collected_data = dict(state.collected_data)
        collected_data[self.data_key] = data.model_dump(mode="json")
        return collected_data

    @staticmethod
    def _step(state: AgentState) -> BookingStep | None:
        if state.current_step is None:
            return None
        try:
            return BookingStep(state.current_step)
        except ValueError:
            return None

    @staticmethod
    def _extract_correction(transcript: str) -> tuple[str, str] | None:
        pickup = _PICKUP_CORRECTION.search(transcript)
        if pickup is not None:
            return "pickup", pickup.group("value").strip(" .")
        destination = _DESTINATION_CORRECTION.search(transcript)
        if destination is not None:
            return "destination", destination.group("value").strip(" .")
        return None

    @staticmethod
    def _understood_correction(
        understanding: UnderstandingResult | None,
    ) -> tuple[str, str] | None:
        if understanding is None or not understanding.corrections:
            return None
        correction = understanding.corrections[0]
        if correction.field is CorrectionField.PICKUP:
            return "pickup", correction.value
        if correction.field is CorrectionField.DESTINATION:
            return "destination", correction.value
        if correction.field is CorrectionField.VEHICLE_TYPE:
            return "vehicle_type", correction.value
        return None

    @staticmethod
    def _parse_vehicle_type(transcript: str) -> VehicleType | None:
        normalized = transcript.casefold()
        for vehicle_type, terms in _VEHICLE_TERMS.items():
            if any(term in normalized for term in terms):
                return vehicle_type
        return None

    @staticmethod
    def _normalize_vehicle_type(value: str) -> VehicleType | None:
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "4_SEAT": VehicleType.FOUR_SEAT,
            "FOUR_SEAT": VehicleType.FOUR_SEAT,
            "7_SEAT": VehicleType.SEVEN_SEAT,
            "SEVEN_SEAT": VehicleType.SEVEN_SEAT,
            "PREMIUM": VehicleType.PREMIUM,
        }
        return aliases.get(normalized)

    @staticmethod
    def _match_candidate(transcript: str, candidates: list) -> Any | None:
        normalized = transcript.casefold().strip()
        number_match = re.search(r"\b([1-9])\b", normalized)
        if number_match is not None:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
        matches = [
            candidate
            for candidate in candidates
            if candidate.display_name.casefold() in normalized
        ]
        return matches[0] if len(matches) == 1 else None
