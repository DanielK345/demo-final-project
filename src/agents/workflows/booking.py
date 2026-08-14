import re
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from src.agents.booking_types import VehicleType
from src.agents.location_policy import is_ambiguous_location_text
from src.agents.phone_policy import extract_valid_mobile_phone
from src.agents.policy import AgentPolicy
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.tools.booking import (
    CancelBookingTool,
    CreateBookingTool,
    EstimateFareTool,
    GetVehicleOptionsTool,
)
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    clear_pending_tool_updates,
    correlate_tool_result,
    normalize_tool_failure,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.maps import SearchPlaceTool
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    EstimateFareResult,
    GetVehicleOptionsResult,
    SearchPlaceResult,
    VehicleOption,
)
from src.agents.understanding.models import (
    ConfirmationIntent,
    CorrectionField,
    UnderstandingResult,
)
from src.agents.vehicle_recommendation import (
    RecommendationReason,
    VehicleRecommendationPort,
    build_vehicle_recommender,
)
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking_models import BookingData, BookingStep
from src.agents.workflows.handoff import HandoffWorkflow

_ROUTE_PATTERN = re.compile(
    r"\btừ\s+(?P<pickup>.+?)\s+(?:đến|tới|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_PASSENGER_PATTERN = re.compile(
    r"\b(?P<count>\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*"
    r"(?:người|hành\s*khách)\b",
    re.IGNORECASE,
)
_CONFIRM_TERMS = ("đúng", "đồng ý", "xác nhận", "đặt đi", "đặt giúp")
_REJECT_TERMS = ("không", "chưa", "hủy", "sai rồi")
_PICKUP_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?đón"
    r"(?:\s+(?:sang|thành|là))?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_DESTINATION_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?(?:đến|đích)"
    r"(?:\s+(?:sang|thành|là))?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_PHONE_CORRECTION = re.compile(
    r"(?:(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:số\s+)?điện\s+thoại"
    r"(?:\s+(?:sang|thành|là))?|(?:số\s+)?điện\s+thoại\s+(?:đúng\s+)?là)"
    r"\s+(?P<value>(?:\+?84|0)(?:[ .-]?\d){9})",
    re.IGNORECASE,
)
_PICKUP_FIELD = re.compile(r"\b(?:điểm\s+)?đón\b", re.IGNORECASE)
_DESTINATION_FIELD = re.compile(r"\b(?:điểm\s+)?(?:đến|đích)\b", re.IGNORECASE)
_PHONE_FIELD = re.compile(r"\b(?:số\s+)?điện\s+thoại\b", re.IGNORECASE)
_GENERIC_CORRECTION = re.compile(
    r"\b(?:tôi\s+muốn\s+)?sửa(?:\s+lại)?\s+thông\s+tin\b",
    re.IGNORECASE,
)
_VEHICLE_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:loại\s+)?xe(?:\s+(?:sang|thành|là))?"
    r"\s+(?P<value>xe\s+máy|(?:ô\s*tô\s*)?[47]\s*chỗ)",
    re.IGNORECASE,
)
_PASSENGER_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay|thực\s+ra)(?:\s+lại)?(?:\s+(?:số\s+)?(?:người|hành\s*khách))?"
    r"(?:\s+(?:sang|thành|là|có))?\s+"
    r"(?P<value>(?:\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)"
    r"\s*(?:người|hành\s*khách))",
    re.IGNORECASE,
)
_VEHICLE_FIELD = re.compile(r"\b(?:loại\s+xe|xe\s+máy|[47]\s*chỗ)\b", re.IGNORECASE)
_PASSENGER_FIELD = re.compile(r"\b(?:(?:số\s+)?người|hành\s*khách)\b", re.IGNORECASE)
_CONFIRM_PATTERN = re.compile(
    r"^(?:(?:vâng|ừ|đúng|đồng\s+ý|xác\s+nhận)(?:\s+rồi)?"
    r"(?:[, ]+(?:đặt(?:\s+xe)?(?:\s+giúp(?:\s+tôi|\s+bác)?)?(?:\s+đi)?).*)?"
    r"|đặt(?:\s+xe)?(?:\s+giúp(?:\s+tôi|\s+bác)?)?(?:\s+đi)?)$",
    re.IGNORECASE,
)
_REJECT_PATTERN = re.compile(
    r"^(?:không|chưa|không\s+đồng\s+ý|không\s+xác\s+nhận|chưa\s+đúng|sai\s+rồi)"
    r"(?:[,.! ]|$)",
    re.IGNORECASE,
)


class RideBookingWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING
    data_key = "booking"

    def __init__(
        self,
        search_place_tool: SearchPlaceTool | None = None,
        estimate_fare_tool: EstimateFareTool | None = None,
        get_vehicle_options_tool: GetVehicleOptionsTool | None = None,
        create_booking_tool: CreateBookingTool | None = None,
        cancel_booking_tool: CancelBookingTool | None = None,
        policy: AgentPolicy | None = None,
        vehicle_recommender: VehicleRecommendationPort | None = None,
    ) -> None:
        self.search_place_tool = search_place_tool or SearchPlaceTool()
        self.estimate_fare_tool = estimate_fare_tool or EstimateFareTool()
        self.get_vehicle_options_tool = get_vehicle_options_tool or GetVehicleOptionsTool()
        self.create_booking_tool = create_booking_tool or CreateBookingTool()
        self.cancel_booking_tool = cancel_booking_tool or CancelBookingTool()
        self.policy = policy or AgentPolicy()
        self.vehicle_recommender = vehicle_recommender or build_vehicle_recommender()

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

        correction = self._extract_correction(transcript)
        if correction is None:
            correction = self._understood_correction(understanding)
        if correction is not None:
            field, value = correction
            return self._begin_correction(state, data, field, value)

        if _GENERIC_CORRECTION.search(transcript):
            return self._ask_correction_field(state, data)

        vehicle_needs_update = self._apply_cross_step_vehicle_needs(
            state,
            data,
            step,
            understanding,
        )
        if vehicle_needs_update is not None:
            return vehicle_needs_update

        if step is BookingStep.WAITING_FOR_PICKUP_RESULT and transcript:
            return self._supersede_place_search(
                state,
                data,
                transcript,
                understanding,
                pickup=True,
            )
        if step is BookingStep.WAITING_FOR_DESTINATION_RESULT and transcript:
            return self._supersede_place_search(
                state,
                data,
                transcript,
                understanding,
                pickup=False,
            )

        if step is BookingStep.SELECT_CORRECTION_FIELD:
            field = self._select_correction_field(transcript)
            if field is None:
                return self._retry_ask(
                    state,
                    data,
                    BookingStep.SELECT_CORRECTION_FIELD,
                    "Bạn muốn sửa điểm đón, điểm đến hay số điện thoại?",
                    confirmation=ConfirmationStatus.REJECTED,
                )
            return self._begin_correction(state, data, field, None)

        if step is BookingStep.COLLECT_PICKUP:
            return self._collect_pickup(state, data, transcript, understanding)
        if step is BookingStep.SELECT_PICKUP_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=True)
        if step is BookingStep.COLLECT_DESTINATION:
            return self._collect_destination(state, data, transcript, understanding)
        if step is BookingStep.SELECT_DESTINATION_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=False)
        if step is BookingStep.COLLECT_VEHICLE:
            return self._collect_vehicle(state, data, transcript, understanding)
        if step is BookingStep.SELECT_VEHICLE_OPTION:
            return self._select_vehicle_option(state, data, transcript)
        if step is BookingStep.COLLECT_PHONE:
            return self._collect_phone(state, data, transcript, understanding)
        if step is BookingStep.CONFIRM:
            return self._handle_confirmation(
                state,
                data,
                transcript,
                understanding,
            )
        if step is BookingStep.CONFIRM_CANCEL:
            return self._confirm_cancellation(state, data, transcript)
        if step in {
            BookingStep.WAITING_FOR_PICKUP_RESULT,
            BookingStep.WAITING_FOR_DESTINATION_RESULT,
            BookingStep.WAITING_FOR_FARE_ESTIMATE,
            BookingStep.WAITING_FOR_VEHICLE_OPTIONS,
            BookingStep.WAITING_FOR_BOOKING_RESULT,
            BookingStep.WAITING_FOR_CANCELLATION_RESULT,
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
            data.destination_query = self._clean_destination_query(understanding.destination_query)
            if understanding.phone_number:
                data.phone_number = understanding.phone_number
            if understanding.vehicle_type:
                data.vehicle_type = understanding.vehicle_type
            if understanding.passenger_count:
                data.passenger_count = understanding.passenger_count
            self._capture_vehicle_needs(data, understanding)
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
            data.destination_query = self._clean_destination_query(route.group("destination"))
            return self._request_place(
                state,
                data,
                query=data.pickup_query,
                operation="pickup",
                waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
            )

        return self._ask(
            state,
            data,
            step=BookingStep.COLLECT_PICKUP,
            message="Bạn muốn đón ở đâu?",
            reason="Ride booking requires a pickup location.",
        )

    def _collect_pickup(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        if (
            understanding is not None
            and understanding.confirmation is not ConfirmationIntent.NOT_APPLICABLE
            and not understanding.pickup_query
        ):
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PICKUP,
                message="Tôi chưa có điểm đón. Bạn muốn đón ở đâu?",
                reason="Confirmation cannot replace a missing pickup location.",
            )
        pickup = understanding.pickup_query if understanding is not None and understanding.pickup_query else transcript
        if understanding is not None and understanding.destination_query:
            data.destination_query = self._clean_destination_query(understanding.destination_query)
        if understanding is not None and understanding.phone_number:
            data.phone_number = understanding.phone_number
        if understanding is not None and understanding.vehicle_type:
            data.vehicle_type = understanding.vehicle_type
        if understanding is not None and understanding.passenger_count:
            data.passenger_count = understanding.passenger_count
        self._capture_vehicle_needs(data, understanding)
        if not pickup:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_PICKUP,
                "Bạn vui lòng nói lại điểm đón.",
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
        if (
            understanding is not None
            and understanding.confirmation is not ConfirmationIntent.NOT_APPLICABLE
            and not understanding.destination_query
        ):
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Tôi chưa có điểm đến. Bạn muốn đi đâu?",
                reason="Confirmation cannot replace a missing destination.",
            )
        destination = (
            understanding.destination_query
            if understanding is not None and understanding.destination_query
            else self._clean_destination_query(transcript)
        )
        if understanding is not None and understanding.phone_number:
            data.phone_number = understanding.phone_number
        if understanding is not None and understanding.vehicle_type:
            data.vehicle_type = understanding.vehicle_type
        if understanding is not None and understanding.passenger_count:
            data.passenger_count = understanding.passenger_count
        self._capture_vehicle_needs(data, understanding)
        if not destination:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_DESTINATION,
                "Bạn vui lòng nói lại điểm đến.",
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
        if is_ambiguous_location_text(query):
            step = BookingStep.COLLECT_PICKUP if operation == "pickup" else BookingStep.COLLECT_DESTINATION
            label = "điểm đón" if operation == "pickup" else "điểm đến"
            return self._ask(
                state,
                data,
                step=step,
                message=f"Bạn vui lòng cung cấp địa chỉ {label} cụ thể.",
                reason=f"The {operation} reference is not a resolvable address.",
            )
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
                "retry_count": 0,
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
            if state.pending_tool_name in {
                ToolName.CREATE_BOOKING,
                ToolName.CANCEL_BOOKING,
            }:
                return self._reconciliation_action(str(exc))
            return await self._handoff(agent_input, state, str(exc))

        if result.status is ToolStatus.ERROR:
            return await self._handle_tool_failure(agent_input, state, data)

        try:
            payload = parse_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))

        step = self._step(state)
        if step is BookingStep.WAITING_FOR_PICKUP_RESULT and isinstance(payload, SearchPlaceResult):
            return self._process_place_result(state, data, payload, pickup=True)
        if step is BookingStep.WAITING_FOR_DESTINATION_RESULT and isinstance(payload, SearchPlaceResult):
            return self._process_place_result(state, data, payload, pickup=False)
        if step is BookingStep.WAITING_FOR_FARE_ESTIMATE and isinstance(payload, EstimateFareResult):
            return self._process_fare_estimate(state, data, payload)
        if step is BookingStep.WAITING_FOR_VEHICLE_OPTIONS and isinstance(payload, GetVehicleOptionsResult):
            return await self._process_vehicle_options(state, data, payload)
        if step is BookingStep.WAITING_FOR_BOOKING_RESULT and isinstance(payload, CreateBookingResult):
            return self._complete_booking(state, data, payload)
        if step is BookingStep.WAITING_FOR_CANCELLATION_RESULT and isinstance(payload, CancelBookingResult):
            return self._complete_cancellation(state, data, payload)
        return await self._handoff(
            agent_input,
            state,
            "Tool result is not valid for the current booking step",
        )

    async def _handle_tool_failure(
        self,
        agent_input: AgentInput,
        state: AgentState,
        data: BookingData,
    ) -> AgentAction:
        result = agent_input.tool_result
        assert result is not None
        failure = normalize_tool_failure(result, state)
        step = self._step(state)
        next_retry = state.retry_count + 1

        if (
            result.tool_name is ToolName.SEARCH_PLACE
            and failure.retryable
            and next_retry < self.policy.retry_limit(result.tool_name)
        ):
            if step is BookingStep.WAITING_FOR_PICKUP_RESULT:
                query = data.pickup_query
                operation = "pickup"
                waiting_step = BookingStep.WAITING_FOR_PICKUP_RESULT
            else:
                query = data.destination_query
                operation = "destination"
                waiting_step = BookingStep.WAITING_FOR_DESTINATION_RESULT
            if query:
                action = self._request_place(
                    state,
                    data,
                    query=query,
                    operation=operation,
                    waiting_step=waiting_step,
                )
                action.state_updates["retry_count"] = next_retry
                return action

        if (
            result.tool_name in {ToolName.ESTIMATE_FARE, ToolName.GET_VEHICLE_OPTIONS}
            and failure.retryable
            and next_retry < self.policy.retry_limit(result.tool_name)
        ):
            action = (
                self._request_vehicle_options(state, data)
                if result.tool_name is ToolName.GET_VEHICLE_OPTIONS
                else self._request_fare_estimate(state, data)
            )
            action.state_updates["retry_count"] = next_retry
            return action

        if result.tool_name in {ToolName.CREATE_BOOKING, ToolName.CANCEL_BOOKING} and (
            failure.retryable or (failure.code or "").casefold() in {"timeout", "unknown_outcome", "connection_lost"}
        ):
            return self._reconciliation_action(f"Unknown {result.tool_name.value} outcome: {failure.message}")

        if result.tool_name is ToolName.CREATE_BOOKING:
            return self._ask(
                state,
                data,
                step=BookingStep.CONFIRM,
                message=("Yêu cầu đặt xe chưa thành công. Bạn có muốn thử xác nhận lại không?"),
                reason=f"Booking failed definitively: {failure.message}",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
                clear_pending=True,
            )

        if result.tool_name is ToolName.CANCEL_BOOKING:
            return self._ask(
                state,
                data,
                step=BookingStep.CONFIRM_CANCEL,
                message="Hủy chuyến chưa thành công. Bạn có muốn thử lại không?",
                reason=f"Cancellation failed definitively: {failure.message}",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
                clear_pending=True,
            )

        return await self._handoff(
            agent_input,
            state,
            f"Critical tool error: {failure.message}",
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
            step = BookingStep.COLLECT_PICKUP if pickup else BookingStep.COLLECT_DESTINATION
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
                f"{index}. {candidate.display_name}" for index, candidate in enumerate(candidates[:3], start=1)
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
            if data.correction_field is CorrectionField.PICKUP:
                return self._finish_correction(
                    state,
                    data,
                    clear_pending=True,
                )
            if data.destination_query:
                return self._request_place(
                    state,
                    data,
                    query=data.destination_query,
                    operation="destination",
                    waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
                )
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Bạn muốn đi đến đâu?",
                reason="The destination is missing.",
                clear_pending=True,
            )

        data.destination = candidates[0]
        data.destination_candidates = []
        if self._same_route(data):
            return self._ask_for_distinct_destination(
                state,
                data,
                clear_pending=True,
            )
        if data.correction_field is CorrectionField.DESTINATION:
            return self._finish_correction(
                state,
                data,
                clear_pending=True,
            )
        return self._after_locations(state, data, clear_pending=True)

    def _supersede_place_search(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
        *,
        pickup: bool,
    ) -> AgentAction:
        understood_value = None
        if understanding is not None:
            understood_value = understanding.pickup_query if pickup else understanding.destination_query
        query = understood_value or transcript
        if pickup:
            data.pickup_query = query
            data.pickup = None
            data.pickup_candidates = []
            operation = "pickup"
            waiting_step = BookingStep.WAITING_FOR_PICKUP_RESULT
        else:
            data.destination_query = query
            data.destination = None
            data.destination_candidates = []
            operation = "destination"
            waiting_step = BookingStep.WAITING_FOR_DESTINATION_RESULT
        self._clear_fare_estimate(data)
        return self._request_place(
            state,
            data,
            query=query,
            operation=operation,
            waiting_step=waiting_step,
        )

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
        step = BookingStep.SELECT_PICKUP_CANDIDATE if pickup else BookingStep.SELECT_DESTINATION_CANDIDATE
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
            if data.correction_field is CorrectionField.PICKUP:
                return self._finish_correction(state, data)
            if data.destination_query:
                return self._request_place(
                    state,
                    data,
                    query=data.destination_query,
                    operation="destination",
                    waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
                )
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Bạn muốn đi đến đâu?",
                reason="The destination is missing.",
            )

        data.destination = candidate
        data.destination_candidates = []
        if self._same_route(data):
            return self._ask_for_distinct_destination(state, data)
        if data.correction_field is CorrectionField.DESTINATION:
            return self._finish_correction(state, data)
        return self._after_locations(state, data)

    def _after_locations(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        if self._same_route(data):
            return self._ask_for_distinct_destination(
                state,
                data,
                clear_pending=clear_pending,
            )
        if data.vehicle_type is None:
            if data.passenger_count is not None:
                return self._request_vehicle_options(state, data)
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_VEHICLE,
                message=("Bạn đi bao nhiêu người, có bao nhiêu hành lý và ưu tiên xe như thế nào?"),
                reason="Vehicle needs are required before requesting Backend options.",
                clear_pending=clear_pending,
            )
        if data.fare_estimate_id is None:
            return self._request_fare_estimate(
                state,
                data,
                clear_pending=clear_pending,
            )
        if not data.phone_number:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PHONE,
                message="Bạn vui lòng cung cấp số điện thoại đặt xe.",
                reason="A phone number is required before confirmation.",
                clear_pending=clear_pending,
            )
        return self._confirmation_action(state, data, clear_pending=clear_pending)

    def _collect_vehicle(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        vehicle = (
            understanding.vehicle_type
            if understanding is not None and understanding.vehicle_type
            else self._extract_vehicle(transcript)
        )
        passenger_count = (
            understanding.passenger_count
            if understanding is not None and understanding.passenger_count
            else self._extract_passenger_count(transcript)
        )
        if passenger_count is not None:
            data.passenger_count = passenger_count
        self._capture_vehicle_needs(data, understanding)
        if vehicle is None and data.passenger_count is not None:
            return self._request_vehicle_options(state, data)
        if vehicle is None:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_VEHICLE,
                "Bạn vui lòng cho biết số người, hành lý hoặc loại xe mong muốn.",
            )
        data.vehicle_type = vehicle
        self._clear_fare_estimate(data)
        return self._request_fare_estimate(state, data)

    def _request_vehicle_options(
        self,
        state: AgentState,
        data: BookingData,
    ) -> AgentAction:
        assert data.pickup is not None
        assert data.destination is not None
        assert data.passenger_count is not None
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.GET_VEHICLE_OPTIONS,
            operation="vehicle-options",
            sequence=state.state_version + 1,
        )
        tool_call = self.get_vehicle_options_tool.build_call(
            call_id,
            pickup_place_id=data.pickup.place_id,
            destination_place_id=data.destination.place_id,
            passenger_count=data.passenger_count,
            luggage_count=data.luggage_count,
            preference=data.vehicle_preference,
        )
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates={
                "current_workflow": self.workflow_type,
                "collected_data": self._store_data(state, data),
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                "retry_count": 0,
                **pending_tool_updates(
                    tool_call,
                    waiting_step=BookingStep.WAITING_FOR_VEHICLE_OPTIONS.value,
                ),
            },
            reason="Backend options are required before recommending a vehicle.",
        )

    async def _process_vehicle_options(
        self,
        state: AgentState,
        data: BookingData,
        result: GetVehicleOptionsResult,
    ) -> AgentAction:
        options = [option for option in result.options if option.available]
        data.vehicle_options = options
        if not options:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_VEHICLE,
                message="Hiện chưa có xe phù hợp. Bạn muốn điều chỉnh nhu cầu không?",
                reason="Backend returned no available vehicle options.",
                clear_pending=True,
            )
        assert data.passenger_count is not None
        recommendation = await self.vehicle_recommender.recommend(
            session_id=state.session_id,
            passenger_count=data.passenger_count,
            luggage_count=data.luggage_count,
            preference=data.vehicle_preference,
            options=options,
        )
        valid_ids = {option.option_id for option in options}
        recommendation_id = recommendation.option_id if recommendation.option_id in valid_ids else None
        data.recommended_vehicle_option_id = recommendation_id
        choices = "; ".join(
            f"{index}. {option.display_name}, {self._format_option_fare(option)}"
            for index, option in enumerate(options, start=1)
        )
        recommendation_text = ""
        if recommendation_id:
            option = next(item for item in options if item.option_id == recommendation_id)
            reason_text = self._recommendation_reason_text(recommendation.reason)
            recommendation_text = f" Tôi đề xuất {option.display_name}{reason_text}."
        return self._ask(
            state,
            data,
            step=BookingStep.SELECT_VEHICLE_OPTION,
            message=f"Hiện có: {choices}.{recommendation_text} Bạn chọn phương án nào?",
            reason="The user must select a Backend-validated vehicle option.",
            clear_pending=True,
        )

    def _select_vehicle_option(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
    ) -> AgentAction:
        option = self._match_vehicle_option(transcript, data)
        if option is None:
            return self._retry_ask(
                state,
                data,
                BookingStep.SELECT_VEHICLE_OPTION,
                "Bạn vui lòng chọn số thứ tự hoặc tên một phương án xe ở trên.",
            )
        data.vehicle_type = option.vehicle_type
        data.selected_vehicle_option_id = option.option_id
        data.vehicle_display_name = option.display_name
        data.fare_estimate_id = option.estimate_id
        data.estimated_fare_amount = option.fare_amount
        data.estimated_currency = option.currency
        data.estimated_eta_minutes = option.eta_minutes
        data.vehicle_options = []
        data.recommended_vehicle_option_id = None
        if data.correction_field is CorrectionField.PASSENGER_COUNT:
            data.correction_field = None
            data.correction_return_step = None
        if data.phone_number is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PHONE,
                message=(
                    f"Bạn đã chọn {option.display_name}, giá dự kiến "
                    f"{self._format_fare(data)}. Bạn vui lòng cung cấp số điện thoại."
                ),
                reason="The user selected a Backend-validated vehicle option.",
            )
        return self._confirmation_action(state, data)

    def _collect_phone(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
        understanding: UnderstandingResult | None,
    ) -> AgentAction:
        phone = (
            understanding.phone_number
            if understanding is not None and understanding.phone_number
            else self._extract_phone(transcript)
        )
        if phone is None:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_PHONE,
                "Số điện thoại chưa hợp lệ. Bạn vui lòng đọc lại.",
            )
        data.phone_number = phone
        if data.correction_field is CorrectionField.PHONE_NUMBER:
            return self._finish_correction(state, data)
        return self._confirmation_action(state, data)

    def _apply_cross_step_vehicle_needs(
        self,
        state: AgentState,
        data: BookingData,
        step: BookingStep | None,
        understanding: UnderstandingResult | None,
    ) -> AgentAction | None:
        """Apply late ride-requirement updates before step-specific parsing.

        A prompt such as COLLECT_PHONE describes the next missing field; it must
        not prevent the user from changing an earlier ride requirement.
        """
        if understanding is None or step not in {
            BookingStep.SELECT_VEHICLE_OPTION,
            BookingStep.COLLECT_PHONE,
            BookingStep.CONFIRM,
        }:
            return None

        passenger_count = understanding.passenger_count
        luggage_count = understanding.luggage_count
        vehicle_preference = understanding.vehicle_preference
        requested_vehicle_type = understanding.vehicle_type
        direct_vehicle_change = (
            step in {BookingStep.COLLECT_PHONE, BookingStep.CONFIRM}
            and requested_vehicle_type is not None
            and requested_vehicle_type != data.vehicle_type
        )
        changed = (
            passenger_count is not None
            and passenger_count != data.passenger_count
        ) or (
            luggage_count is not None
            and luggage_count != data.luggage_count
        ) or (
            vehicle_preference is not None
            and vehicle_preference != data.vehicle_preference
        )
        if not changed and not direct_vehicle_change:
            return None

        if direct_vehicle_change and not changed:
            data.vehicle_type = requested_vehicle_type
            self._clear_vehicle_option_selection(data)
            self._clear_fare_estimate(data)
            if data.pickup is None:
                return self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_PICKUP,
                    message="Tôi đã đổi loại xe. Bạn muốn đón ở đâu?",
                    reason="Vehicle type changed but pickup is missing.",
                )
            if data.destination is None:
                return self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_DESTINATION,
                    message="Tôi đã đổi loại xe. Bạn muốn đến đâu?",
                    reason="Vehicle type changed but destination is missing.",
                )
            return self._request_fare_estimate(state, data)

        if passenger_count is not None:
            data.passenger_count = passenger_count
        if luggage_count is not None:
            data.luggage_count = luggage_count
        if vehicle_preference is not None:
            data.vehicle_preference = vehicle_preference
        self._clear_vehicle_selection(data)
        self._clear_fare_estimate(data)

        if data.passenger_count is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_VEHICLE,
                message=(
                    "Tôi đã cập nhật nhu cầu chuyến đi. "
                    "Bạn vui lòng cho biết tổng số hành khách."
                ),
                reason="Updated vehicle needs require a passenger count.",
            )
        if data.pickup is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PICKUP,
                message="Tôi đã cập nhật nhu cầu chuyến đi. Bạn muốn đón ở đâu?",
                reason="Updated vehicle needs but pickup is missing.",
            )
        if data.destination is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Tôi đã cập nhật nhu cầu chuyến đi. Bạn muốn đến đâu?",
                reason="Updated vehicle needs but destination is missing.",
            )
        return self._request_vehicle_options(state, data)

    def _request_fare_estimate(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        assert data.pickup is not None
        assert data.destination is not None
        assert data.vehicle_type is not None
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.ESTIMATE_FARE,
            operation="fare",
            sequence=state.state_version + 1,
        )
        tool_call = self.estimate_fare_tool.build_call(
            call_id,
            pickup_place_id=data.pickup.place_id,
            destination_place_id=data.destination.place_id,
            vehicle_type=data.vehicle_type,
        )
        updates: dict[str, Any] = {
            "current_workflow": self.workflow_type,
            "collected_data": self._store_data(state, data),
            "confirmation": ConfirmationStatus.NOT_REQUESTED,
            "retry_count": 0,
            **pending_tool_updates(
                tool_call,
                waiting_step=BookingStep.WAITING_FOR_FARE_ESTIMATE.value,
            ),
        }
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates=updates,
            reason="A current fare estimate is required before booking confirmation.",
        )

    def _process_fare_estimate(
        self,
        state: AgentState,
        data: BookingData,
        result: EstimateFareResult,
    ) -> AgentAction:
        data.fare_estimate_id = result.estimate_id
        data.estimated_fare_amount = result.fare_amount
        data.estimated_currency = result.currency
        data.estimated_eta_minutes = result.eta_minutes
        data.estimated_distance_km = result.distance_km
        if data.correction_field is CorrectionField.VEHICLE_TYPE:
            data.correction_field = None
            data.correction_return_step = None
        if data.phone_number is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PHONE,
                message=(f"Giá dự kiến là {self._format_fare(data)}. Bạn vui lòng cung cấp số điện thoại đặt xe."),
                reason="A phone number is required after fare estimation.",
                clear_pending=True,
            )
        return self._confirmation_action(state, data, clear_pending=True)

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
        assert data.fare_estimate_id is not None
        return self._ask(
            state,
            data,
            step=BookingStep.CONFIRM,
            message=(
                f"Bạn xác nhận đặt xe đón tại {data.pickup.display_name} "
                f"và đến {data.destination.display_name}, loại "
                f"{self._vehicle_label(data)}, giá dự kiến "
                f"{self._format_fare(data)}"
                f"{self._passenger_confirmation(data)}, đúng không?"
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
        rejected = bool(_REJECT_PATTERN.match(normalized)) or (
            understanding is not None and understanding.confirmation is ConfirmationIntent.REJECT
        )
        confirmed = bool(_CONFIRM_PATTERN.fullmatch(normalized.strip(" .!?"))) or (
            understanding is not None and understanding.confirmation is ConfirmationIntent.CONFIRM
        )
        if rejected:
            return self._ask_correction_field(state, data)
        if not confirmed:
            return self._retry_ask(
                state,
                data,
                BookingStep.CONFIRM,
                "Bạn vui lòng xác nhận đồng ý hoặc nói thông tin cần sửa.",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
            )
        if (
            data.pickup is None
            or data.destination is None
            or data.vehicle_type is None
            or data.fare_estimate_id is None
            or data.phone_number is None
        ):
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
        tool_call = self.create_booking_tool.build_call(
            call_id,
            pickup_place_id=data.pickup.place_id,
            destination_place_id=data.destination.place_id,
            phone_number=data.phone_number,
            vehicle_type=data.vehicle_type,
            vehicle_option_id=data.selected_vehicle_option_id,
            fare_estimate_id=data.fare_estimate_id,
            idempotency_key=self._idempotency_key(
                state.session_id,
                "create",
                data.fare_estimate_id,
                data.phone_number,
            ),
            passenger_count=data.passenger_count,
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
        data.eta_minutes = result.eta_minutes
        data.fare_amount = result.fare_amount
        data.currency = result.currency
        data.completed_booking_call_id = state.pending_tool_call_id
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
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                **clear_pending_tool_updates(),
            },
            reason="The booking tool returned a successful result.",
        )

    def _confirm_cancellation(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
    ) -> AgentAction:
        normalized = transcript.casefold().strip(" .!?")
        if _REJECT_PATTERN.match(normalized):
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Tôi sẽ giữ nguyên chuyến xe đã đặt.",
                state_updates={
                    "current_workflow": None,
                    "current_step": None,
                    "confirmation": ConfirmationStatus.NOT_REQUESTED,
                    "retry_count": 0,
                },
                reason="The user rejected booking cancellation.",
            )
        if not _CONFIRM_PATTERN.fullmatch(normalized):
            return self._retry_ask(
                state,
                data,
                BookingStep.CONFIRM_CANCEL,
                "Bạn vui lòng xác nhận có muốn hủy chuyến đã đặt không.",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
            )
        assert data.booking_id is not None
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.CANCEL_BOOKING,
            operation="cancel",
            sequence=state.state_version + 1,
        )
        tool_call = self.cancel_booking_tool.build_call(
            call_id,
            booking_id=data.booking_id,
            idempotency_key=self._idempotency_key(
                state.session_id,
                "cancel",
                data.booking_id,
            ),
        )
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates={
                "current_workflow": self.workflow_type,
                "confirmation": ConfirmationStatus.CONFIRMED,
                **pending_tool_updates(
                    tool_call,
                    waiting_step=BookingStep.WAITING_FOR_CANCELLATION_RESULT.value,
                ),
            },
            reason="The user explicitly confirmed booking cancellation.",
        )

    def _complete_cancellation(
        self,
        state: AgentState,
        data: BookingData,
        result: CancelBookingResult,
    ) -> AgentAction:
        if result.booking_id != data.booking_id:
            return self._reconciliation_action("Cancellation returned another booking ID")
        data.booking_status = result.status
        data.completed_cancellation_call_id = state.pending_tool_call_id
        return AgentAction(
            action_type=ActionType.RESPOND,
            message="Chuyến xe đã được hủy thành công.",
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
                "retry_count": 0,
                **clear_pending_tool_updates(),
            },
            reason="The cancellation tool returned a correlated success result.",
        )

    def _ask_correction_field(
        self,
        state: AgentState,
        data: BookingData,
    ) -> AgentAction:
        data.correction_field = None
        data.correction_return_step = BookingStep.CONFIRM if self._has_complete_booking(data) else None
        action = self._ask(
            state,
            data,
            step=BookingStep.SELECT_CORRECTION_FIELD,
            message=("Bạn muốn sửa điểm đón, điểm đến, số người, loại xe hay số điện thoại?"),
            reason="The user requested a booking correction without a field.",
            confirmation=ConfirmationStatus.REJECTED,
        )
        action.state_updates["retry_count"] = 0
        return action

    def _begin_correction(
        self,
        state: AgentState,
        data: BookingData,
        field: CorrectionField,
        value: str | None,
    ) -> AgentAction:
        if data.correction_return_step is None and self._has_complete_booking(data):
            data.correction_return_step = BookingStep.CONFIRM
        data.correction_field = field

        if field is CorrectionField.PICKUP:
            data.pickup_query = value
            data.pickup = None
            data.pickup_candidates = []
            self._clear_fare_estimate(data)
            if value is None:
                action = self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_PICKUP,
                    message="Bạn muốn đổi điểm đón thành địa chỉ nào?",
                    reason="The corrected pickup value is missing.",
                )
            else:
                action = self._request_place(
                    state,
                    data,
                    query=value,
                    operation="pickup",
                    waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
                )
        elif field is CorrectionField.DESTINATION:
            data.destination_query = value
            data.destination = None
            data.destination_candidates = []
            self._clear_fare_estimate(data)
            if value is None:
                action = self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_DESTINATION,
                    message="Bạn muốn đổi điểm đến thành địa chỉ nào?",
                    reason="The corrected destination value is missing.",
                )
            else:
                action = self._request_place(
                    state,
                    data,
                    query=value,
                    operation="destination",
                    waiting_step=BookingStep.WAITING_FOR_DESTINATION_RESULT,
                )
        elif field is CorrectionField.PHONE_NUMBER:
            data.phone_number = None
            phone = self._extract_phone(value or "")
            if phone is None:
                action = self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_PHONE,
                    message="Bạn vui lòng cung cấp số điện thoại mới.",
                    reason="The corrected phone number is missing or invalid.",
                )
            else:
                data.phone_number = phone
                action = self._finish_correction(state, data)
        elif field is CorrectionField.VEHICLE_TYPE:
            data.vehicle_type = self._extract_vehicle(value or "")
            self._clear_fare_estimate(data)
            if data.vehicle_type is None:
                action = self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_VEHICLE,
                    message="Bạn muốn đổi sang xe máy, ô tô 4 chỗ hay ô tô 7 chỗ?",
                    reason="The corrected vehicle type is missing or invalid.",
                )
            else:
                action = self._request_fare_estimate(state, data)
        elif field is CorrectionField.PASSENGER_COUNT:
            passenger_count = self._parse_passenger_count(value or "")
            if passenger_count is None:
                action = self._ask(
                    state,
                    data,
                    step=BookingStep.COLLECT_VEHICLE,
                    message="Bạn vui lòng cho biết tổng số hành khách mới.",
                    reason="The corrected passenger count is missing or invalid.",
                )
            else:
                data.passenger_count = passenger_count
                self._clear_vehicle_selection(data)
                self._clear_fare_estimate(data)
                action = self._request_vehicle_options(state, data)
        else:  # pragma: no cover - CorrectionField is exhaustively handled above.
            raise ValueError(f"unsupported booking correction field: {field}")

        action.state_updates["retry_count"] = 0
        return action

    def _finish_correction(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        return_step = data.correction_return_step
        data.correction_field = None
        data.correction_return_step = None
        if return_step is BookingStep.CONFIRM and self._has_complete_booking(data):
            return self._confirmation_action(
                state,
                data,
                clear_pending=clear_pending,
            )
        return self._continue_booking(state, data, clear_pending=clear_pending)

    def _continue_booking(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        if data.pickup is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PICKUP,
                message="Bạn muốn đón ở đâu?",
                reason="The pickup location is missing after correction.",
                clear_pending=clear_pending,
            )
        if data.destination is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Bạn muốn đi đến đâu?",
                reason="The destination is missing after correction.",
                clear_pending=clear_pending,
            )
        if data.vehicle_type is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_VEHICLE,
                message="Bạn vui lòng cho biết số người, hành lý hoặc loại xe mong muốn.",
                reason="The vehicle type is missing after correction.",
                clear_pending=clear_pending,
            )
        if data.fare_estimate_id is None:
            return self._request_fare_estimate(
                state,
                data,
                clear_pending=clear_pending,
            )
        if data.phone_number is None:
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_PHONE,
                message="Bạn vui lòng cung cấp số điện thoại đặt xe.",
                reason="The phone number is missing after correction.",
                clear_pending=clear_pending,
            )
        return self._confirmation_action(
            state,
            data,
            clear_pending=clear_pending,
        )

    @staticmethod
    def _has_complete_booking(data: BookingData) -> bool:
        return (
            data.pickup is not None
            and data.destination is not None
            and data.vehicle_type is not None
            and data.fare_estimate_id is not None
            and data.phone_number is not None
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
            "retry_count": 0,
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
        if state.retry_count + 1 >= self.policy.max_retry_count:
            updates: dict[str, Any] = {
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "HANDOFF_REQUIRED",
                "confirmation": ConfirmationStatus.NOT_REQUESTED,
            }
            if clear_pending:
                updates.update(clear_pending_tool_updates())
            return AgentAction(
                action_type=ActionType.HANDOFF,
                message="Tôi sẽ chuyển bạn tới tổng đài viên để hỗ trợ tiếp.",
                state_updates=updates,
                reason="Booking clarification retry limit was reached.",
            )
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
    def _extract_phone(transcript: str) -> str | None:
        return extract_valid_mobile_phone(transcript)

    @staticmethod
    def _extract_vehicle(value: str) -> VehicleType | None:
        normalized = " ".join(value.casefold().split())
        serialized = {
            VehicleType.MOTORBIKE.value.casefold(): VehicleType.MOTORBIKE,
            VehicleType.CAR_4.value.casefold(): VehicleType.CAR_4,
            VehicleType.CAR_7.value.casefold(): VehicleType.CAR_7,
        }
        if normalized in serialized:
            return serialized[normalized]
        if "xe máy" in normalized or "xe may" in normalized:
            return VehicleType.MOTORBIKE
        if re.search(r"\b(?:4|bốn)\s*chỗ\b", normalized):
            return VehicleType.CAR_4
        if re.search(r"\b(?:7|bảy)\s*chỗ\b", normalized):
            return VehicleType.CAR_7
        return None

    @staticmethod
    def _extract_passenger_count(value: str) -> int | None:
        match = _PASSENGER_PATTERN.search(value)
        if match is None:
            return None
        token = match.group("count").casefold()
        words = {
            "một": 1,
            "hai": 2,
            "ba": 3,
            "bốn": 4,
            "năm": 5,
            "sáu": 6,
            "bảy": 7,
            "tám": 8,
            "chín": 9,
            "mười": 10,
        }
        return words.get(token, int(token) if token.isdigit() else None)

    @staticmethod
    def _parse_passenger_count(value: str) -> int | None:
        extracted = RideBookingWorkflow._extract_passenger_count(value)
        if extracted is not None:
            return extracted
        normalized = value.casefold().strip(" .,;!?")
        words = {
            "một": 1,
            "hai": 2,
            "ba": 3,
            "bốn": 4,
            "năm": 5,
            "sáu": 6,
            "bảy": 7,
            "tám": 8,
            "chín": 9,
            "mười": 10,
        }
        if normalized in words:
            return words[normalized]
        if normalized.isdigit() and 1 <= int(normalized) <= 50:
            return int(normalized)
        return None

    def _match_vehicle_option(
        self,
        transcript: str,
        data: BookingData,
    ) -> VehicleOption | None:
        normalized = transcript.casefold().strip(" .!?")
        if _CONFIRM_PATTERN.fullmatch(normalized) and data.recommended_vehicle_option_id:
            return next(
                (option for option in data.vehicle_options if option.option_id == data.recommended_vehicle_option_id),
                None,
            )
        number = re.search(r"\b([1-9])\b", normalized)
        if number:
            index = int(number.group(1)) - 1
            if 0 <= index < len(data.vehicle_options):
                return data.vehicle_options[index]
        matches = [
            option
            for option in data.vehicle_options
            if option.option_id.casefold() in normalized
            or option.display_name.casefold() in normalized
            or option.vehicle_type.casefold() in normalized
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _capture_vehicle_needs(
        data: BookingData,
        understanding: UnderstandingResult | None,
    ) -> None:
        if understanding is None:
            return
        if understanding.luggage_count is not None:
            data.luggage_count = understanding.luggage_count
        if understanding.vehicle_preference:
            data.vehicle_preference = understanding.vehicle_preference

    @staticmethod
    def _clear_vehicle_selection(data: BookingData) -> None:
        data.vehicle_type = None
        RideBookingWorkflow._clear_vehicle_option_selection(data)

    @staticmethod
    def _clear_vehicle_option_selection(data: BookingData) -> None:
        data.selected_vehicle_option_id = None
        data.vehicle_display_name = None
        data.vehicle_options = []
        data.recommended_vehicle_option_id = None

    @staticmethod
    def _format_option_fare(option: VehicleOption) -> str:
        if option.currency == "VND":
            return f"{option.fare_amount:,.0f} đồng".replace(",", ".")
        return f"{option.fare_amount:,.0f} {option.currency}"

    @staticmethod
    def _recommendation_reason_text(
        reason: RecommendationReason | None,
    ) -> str:
        return {
            RecommendationReason.PASSENGER_FIT: " vì phù hợp số hành khách",
            RecommendationReason.LUGGAGE_FIT: " vì phù hợp lượng hành lý",
            RecommendationReason.COMFORT: " theo ưu tiên thoải mái của bạn",
            RecommendationReason.ECONOMY: " theo ưu tiên tiết kiệm của bạn",
            RecommendationReason.PREMIUM: " theo ưu tiên cao cấp của bạn",
            None: "",
        }[reason]

    @staticmethod
    def _passenger_confirmation(data: BookingData) -> str:
        if data.passenger_count is None:
            return ""
        return f", cho {data.passenger_count} hành khách"

    @staticmethod
    def _vehicle_label(data: BookingData) -> str:
        if data.vehicle_display_name:
            return data.vehicle_display_name
        try:
            return VehicleType(data.vehicle_type).spoken_label
        except ValueError:
            return data.vehicle_type or "loại xe đã chọn"

    @staticmethod
    def _clean_destination_query(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip(" .,;")
        cleaned = re.sub(
            r"[,;]?\s+(?:cho\s+)?(?:\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)"
            r"\s*(?:người|hành\s*khách)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[,;]?\s*(?:(?:đi|bằng|với)\s+)?"
            r"(?:xe\s+máy|xe\s+may|(?:ô\s*tô|xe)?\s*[47]\s*chỗ)"
            r"(?:\s+(?:giúp\s+tôi|nhé|ạ))?$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip(" .,;")

    @staticmethod
    def _clear_fare_estimate(data: BookingData) -> None:
        data.fare_estimate_id = None
        data.estimated_fare_amount = None
        data.estimated_currency = None
        data.estimated_eta_minutes = None
        data.estimated_distance_km = None

    @staticmethod
    def _same_route(data: BookingData) -> bool:
        return (
            data.pickup is not None
            and data.destination is not None
            and data.pickup.place_id == data.destination.place_id
        )

    def _ask_for_distinct_destination(
        self,
        state: AgentState,
        data: BookingData,
        *,
        clear_pending: bool = False,
    ) -> AgentAction:
        data.destination_query = None
        data.destination = None
        data.destination_candidates = []
        self._clear_fare_estimate(data)
        return self._ask(
            state,
            data,
            step=BookingStep.COLLECT_DESTINATION,
            message="Điểm đến phải khác điểm đón. Bạn muốn đi đến đâu?",
            reason="Pickup and destination cannot be the same resolved place.",
            clear_pending=clear_pending,
        )

    @staticmethod
    def _format_fare(data: BookingData) -> str:
        amount = data.estimated_fare_amount
        currency = data.estimated_currency or "VND"
        if amount is None:
            return "chưa xác định"
        if currency == "VND":
            return f"{amount:,.0f} đồng".replace(",", ".")
        return f"{amount:,.0f} {currency}"

    @staticmethod
    def _idempotency_key(session_id: str, operation: str, *values: str) -> str:
        evidence = "|".join((session_id, operation, *values))
        return f"agent-{operation}-{sha256(evidence.encode()).hexdigest()[:24]}"

    @staticmethod
    def _reconciliation_action(reason: str) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message=("Tôi cần kiểm tra trạng thái giao dịch đang xử lý và sẽ chuyển bạn tới tổng đài viên."),
            state_updates={
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "RECONCILIATION_REQUIRED",
            },
            reason=reason,
        )

    @staticmethod
    def _extract_correction(
        transcript: str,
    ) -> tuple[CorrectionField, str | None] | None:
        pickup = _PICKUP_CORRECTION.search(transcript)
        if pickup is not None:
            return CorrectionField.PICKUP, pickup.group("value").strip(" .")
        destination = _DESTINATION_CORRECTION.search(transcript)
        if destination is not None:
            return (
                CorrectionField.DESTINATION,
                destination.group("value").strip(" ."),
            )
        phone = _PHONE_CORRECTION.search(transcript)
        if phone is not None:
            return CorrectionField.PHONE_NUMBER, phone.group("value").strip(" .")
        vehicle = _VEHICLE_CORRECTION.search(transcript)
        if vehicle is not None:
            parsed = RideBookingWorkflow._extract_vehicle(vehicle.group("value"))
            return CorrectionField.VEHICLE_TYPE, parsed.value if parsed else None
        passenger = _PASSENGER_CORRECTION.search(transcript)
        if passenger is not None:
            return CorrectionField.PASSENGER_COUNT, passenger.group("value").strip(" .")

        normalized = transcript.casefold()
        has_command = any(term in normalized for term in ("đổi", "sửa", "thay"))
        if has_command:
            field = RideBookingWorkflow._select_correction_field(transcript)
            if field is not None:
                return field, None
        return None

    @staticmethod
    def _understood_correction(
        understanding: UnderstandingResult | None,
    ) -> tuple[CorrectionField, str | None] | None:
        if understanding is None or not understanding.corrections:
            return None
        correction = understanding.corrections[0]
        return correction.field, correction.value

    @staticmethod
    def _select_correction_field(transcript: str) -> CorrectionField | None:
        if _PICKUP_FIELD.search(transcript):
            return CorrectionField.PICKUP
        if _DESTINATION_FIELD.search(transcript):
            return CorrectionField.DESTINATION
        if _PHONE_FIELD.search(transcript):
            return CorrectionField.PHONE_NUMBER
        if _VEHICLE_FIELD.search(transcript):
            return CorrectionField.VEHICLE_TYPE
        if _PASSENGER_FIELD.search(transcript):
            return CorrectionField.PASSENGER_COUNT
        return None

    @staticmethod
    def _match_candidate(transcript: str, candidates: list) -> Any | None:
        normalized = transcript.casefold().strip()
        number_match = re.search(r"\b([1-9])\b", normalized)
        if number_match is not None:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(candidates):
                return candidates[index]
        matches = [candidate for candidate in candidates if candidate.display_name.casefold() in normalized]
        if not matches:
            return None
        matches.sort(key=lambda candidate: len(candidate.display_name), reverse=True)
        if len(matches) > 1 and len(matches[0].display_name) == len(matches[1].display_name):
            return None
        return matches[0]
