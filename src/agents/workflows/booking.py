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
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking_models import BookingData, BookingStep
from src.agents.workflows.handoff import HandoffWorkflow

_ROUTE_PATTERN = re.compile(
    r"\btừ\s+(?P<pickup>.+?)\s+(?:đến|tới|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
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
        if correction is not None:
            field, value = correction
            return self._apply_correction(state, data, field, value)

        if step is BookingStep.COLLECT_PICKUP:
            return self._collect_pickup(state, data, transcript)
        if step is BookingStep.SELECT_PICKUP_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=True)
        if step is BookingStep.COLLECT_DESTINATION:
            return self._collect_destination(state, data, transcript)
        if step is BookingStep.SELECT_DESTINATION_CANDIDATE:
            return self._select_candidate(state, data, transcript, pickup=False)
        if step is BookingStep.COLLECT_PHONE:
            return self._collect_phone(state, data, transcript)
        if step is BookingStep.CONFIRM:
            return self._handle_confirmation(state, data, transcript)
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

        return self._start_booking(state, data, transcript)

    def _start_booking(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
    ) -> AgentAction:
        route = _ROUTE_PATTERN.search(transcript)
        if route is not None:
            data.pickup_query = route.group("pickup").strip(" .")
            data.destination_query = route.group("destination").strip(" .")
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
    ) -> AgentAction:
        if not transcript:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_PICKUP,
                "Bạn vui lòng nói lại điểm đón.",
            )
        data.pickup_query = transcript
        data.pickup = None
        data.pickup_candidates = []
        return self._request_place(
            state,
            data,
            query=transcript,
            operation="pickup",
            waiting_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
        )

    def _collect_destination(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
    ) -> AgentAction:
        if not transcript:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_DESTINATION,
                "Bạn vui lòng nói lại điểm đến.",
            )
        data.destination_query = transcript
        data.destination = None
        data.destination_candidates = []
        return self._request_place(
            state,
            data,
            query=transcript,
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
            return self._ask(
                state,
                data,
                step=BookingStep.COLLECT_DESTINATION,
                message="Bạn muốn đi đến đâu?",
                reason="The destination is missing.",
            )

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

    def _collect_phone(
        self,
        state: AgentState,
        data: BookingData,
        transcript: str,
    ) -> AgentAction:
        phone = self._extract_phone(transcript)
        if phone is None:
            return self._retry_ask(
                state,
                data,
                BookingStep.COLLECT_PHONE,
                "Số điện thoại chưa hợp lệ. Bạn vui lòng đọc lại.",
            )
        data.phone_number = phone
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
        return self._ask(
            state,
            data,
            step=BookingStep.CONFIRM,
            message=(
                f"Bạn xác nhận đặt xe đón tại {data.pickup.display_name} "
                f"và đến {data.destination.display_name}, đúng không?"
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
    ) -> AgentAction:
        normalized = transcript.casefold()
        if any(term in normalized for term in _REJECT_TERMS):
            return self._ask(
                state,
                data,
                step=BookingStep.CONFIRM,
                message="Bạn muốn sửa điểm đón hay điểm đến?",
                reason="The user rejected the booking details.",
                confirmation=ConfirmationStatus.REJECTED,
            )
        if not any(term in normalized for term in _CONFIRM_TERMS):
            return self._retry_ask(
                state,
                data,
                BookingStep.CONFIRM,
                "Bạn vui lòng xác nhận đồng ý hoặc nói thông tin cần sửa.",
                confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
            )
        if data.pickup is None or data.destination is None or data.phone_number is None:
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
    def _extract_phone(transcript: str) -> str | None:
        match = _PHONE_PATTERN.search(transcript)
        if match is None:
            return None
        phone = re.sub(r"\D", "", match.group())
        if phone.startswith("84"):
            phone = f"0{phone[2:]}"
        return phone

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
