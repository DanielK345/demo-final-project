import re
from typing import Any

from pydantic import ValidationError

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
from src.agents.state import AgentState
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    ToolResultMismatchError,
    clear_pending_tool_updates,
    correlate_tool_result,
    normalize_tool_failure,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.schemas import LookupTripResult, TripMatch
from src.agents.tools.trip import LookupTripTool
from src.agents.understanding.models import UnderstandingResult
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking_models import BookingData
from src.agents.workflows.handoff import HandoffWorkflow
from src.agents.workflows.trip_lookup_models import TripLookupData, TripLookupStep

_BOOKING_ID_LABEL_PATTERN = re.compile(
    r"(?:mã\s+(?:chuyến|đặt\s*xe)|booking(?:\s*id)?)\s*(?:là|:|#)?\s*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9_-]{2,})",
    re.IGNORECASE,
)
_STANDALONE_BOOKING_ID_PATTERN = re.compile(r"^(?P<value>(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9][A-Za-z0-9_-]{3,})$")


class TripLookupWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.TRIP_LOOKUP
    data_key = "trip_lookup"

    def __init__(
        self,
        lookup_tool: LookupTripTool | None = None,
        policy: AgentPolicy | None = None,
    ) -> None:
        self.lookup_tool = lookup_tool or LookupTripTool()
        self.policy = policy or AgentPolicy()

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
            return await self._handoff(agent_input, state, "Invalid trip lookup state")

        if agent_input.tool_result is not None:
            return await self._handle_tool_result(agent_input, state, data)

        step = self._step(state)
        if step is TripLookupStep.WAITING_FOR_TRIP_RESULT:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang chờ kết quả tra cứu. Bạn vui lòng đợi một chút.",
                reason="The workflow is waiting for a trip tool result.",
            )
        if step is TripLookupStep.SELECT_TRIP:
            return self._select_trip(state, data, agent_input.transcript)
        if step is TripLookupStep.COMPLETE:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message="Thông tin chuyến đã được tra cứu.",
                reason="The trip lookup workflow is already complete.",
            )

        identifier = self._understood_identifier(understanding)
        if identifier is None:
            identifier = self._extract_identifier(agent_input.transcript)
        if identifier is None:
            identifier = self._contextual_identifier(state, data)
        if identifier is None:
            return self._ask_for_identifier(state, data)

        identifier_type, value = identifier
        if identifier_type == "phone_number":
            data.phone_number = value
            data.booking_id = None
        else:
            data.booking_id = value
            data.phone_number = None
        return self._request_lookup(state, data)

    def _request_lookup(
        self,
        state: AgentState,
        data: TripLookupData,
        *,
        retry_count: int | None = None,
    ) -> AgentAction:
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.LOOKUP_TRIP,
            operation="trip",
            sequence=state.state_version + 1,
        )
        tool_call = self.lookup_tool.build_call(
            call_id,
            booking_id=data.booking_id,
            phone_number=data.phone_number,
        )
        updates: dict[str, Any] = {
            "current_workflow": self.workflow_type,
            "collected_data": self._store_data(state, data),
            "retry_count": retry_count if retry_count is not None else 0,
            **pending_tool_updates(
                tool_call,
                waiting_step=TripLookupStep.WAITING_FOR_TRIP_RESULT.value,
            ),
        }
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates=updates,
            reason="A validated identifier is available for trip lookup.",
        )

    async def _handle_tool_result(
        self,
        agent_input: AgentInput,
        state: AgentState,
        data: TripLookupData,
    ) -> AgentAction:
        result = agent_input.tool_result
        assert result is not None
        try:
            correlate_tool_result(result, state)
        except ToolResultMismatchError:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đã bỏ qua kết quả tra cứu cũ và vẫn đang chờ kết quả mới.",
                reason="A stale trip result was ignored without clearing the pending call.",
            )
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))

        if self._step(state) is not TripLookupStep.WAITING_FOR_TRIP_RESULT:
            return await self._handoff(
                agent_input,
                state,
                "Trip tool result is not valid for the current workflow step",
            )

        if result.status is ToolStatus.ERROR:
            failure = normalize_tool_failure(result, state)
            next_retry = state.retry_count + 1
            if failure.retryable and next_retry < self.policy.retry_limit(ToolName.LOOKUP_TRIP):
                return self._request_lookup(state, data, retry_count=next_retry)
            return await self._handoff(
                agent_input,
                state,
                f"Trip lookup tool failed: {failure.message}",
            )

        try:
            payload = parse_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))
        if not isinstance(payload, LookupTripResult):
            return await self._handoff(
                agent_input,
                state,
                "Unexpected payload type for trip lookup",
            )
        if not payload.found:
            data.booking_id = None
            data.phone_number = None
            data.found_booking_id = None
            data.trip_status = None
            data.eta_minutes = None
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=("Tôi chưa tìm thấy chuyến phù hợp. Bạn vui lòng kiểm tra lại mã chuyến hoặc số điện thoại."),
                state_updates={
                    "current_workflow": self.workflow_type,
                    "current_step": TripLookupStep.COLLECT_IDENTIFIER.value,
                    "collected_data": self._store_data(state, data),
                    "retry_count": state.retry_count + 1,
                    **clear_pending_tool_updates(),
                },
                reason="No trip matched the supplied identifier.",
            )

        matches = self._matches(payload)
        if len(matches) > 1:
            data.trip_candidates = matches
            choices = "; ".join(
                f"{index}. {self._trip_label(match, index)}" for index, match in enumerate(matches[:3], start=1)
            )
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=f"Tôi tìm thấy nhiều chuyến: {choices}. Bạn chọn chuyến nào?",
                state_updates={
                    "current_workflow": self.workflow_type,
                    "current_step": TripLookupStep.SELECT_TRIP.value,
                    "collected_data": self._store_data(state, data),
                    "retry_count": 0,
                    **clear_pending_tool_updates(),
                },
                reason="Multiple trips matched without exposing booking identifiers.",
            )
        match = matches[0]
        return self._complete_lookup(state, data, match, result.call_id)

    def _complete_lookup(
        self,
        state: AgentState,
        data: TripLookupData,
        match: TripMatch,
        call_id: str,
    ) -> AgentAction:
        data.found_booking_id = match.booking_id
        data.trip_status = match.status
        data.eta_minutes = match.eta_minutes
        data.trip_candidates = []
        data.completed_lookup_call_id = call_id
        eta_message = f" Thời gian dự kiến là {match.eta_minutes} phút." if match.eta_minutes is not None else ""
        status_message = self._status_label(match.status)
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=f"Trạng thái chuyến hiện tại là {status_message}.{eta_message}",
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                "retry_count": 0,
                **clear_pending_tool_updates(),
            },
            reason="Trip status and ETA came from the validated tool result.",
        )

    def _select_trip(
        self,
        state: AgentState,
        data: TripLookupData,
        transcript: str,
    ) -> AgentAction:
        match = self._match_trip(transcript, data.trip_candidates)
        if match is None:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn vui lòng chọn số thứ tự của chuyến cần xem.",
                state_updates={
                    "current_workflow": self.workflow_type,
                    "current_step": TripLookupStep.SELECT_TRIP.value,
                    "retry_count": state.retry_count + 1,
                },
                reason="The selected trip is unclear.",
            )
        data.booking_id = match.booking_id
        data.phone_number = None
        data.trip_candidates = []
        return self._request_lookup(state, data, retry_count=0)

    def _ask_for_identifier(
        self,
        state: AgentState,
        data: TripLookupData,
    ) -> AgentAction:
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn vui lòng cung cấp mã chuyến hoặc số điện thoại đặt xe.",
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": TripLookupStep.COLLECT_IDENTIFIER.value,
                "collected_data": self._store_data(state, data),
            },
            reason="A trip identifier is required before lookup.",
        )

    async def _handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
        reason: str,
    ) -> AgentAction:
        action = await HandoffWorkflow().handle(agent_input, state)
        action.reason = reason
        return action

    def _load_data(self, state: AgentState) -> TripLookupData:
        return TripLookupData.model_validate(state.collected_data.get(self.data_key, {}))

    def _store_data(
        self,
        state: AgentState,
        data: TripLookupData,
    ) -> dict[str, Any]:
        collected_data = dict(state.collected_data)
        collected_data[self.data_key] = data.model_dump(mode="json")
        return collected_data

    @staticmethod
    def _step(state: AgentState) -> TripLookupStep | None:
        if state.current_step is None:
            return None
        try:
            return TripLookupStep(state.current_step)
        except ValueError:
            return None

    @staticmethod
    def _extract_identifier(transcript: str) -> tuple[str, str] | None:
        phone = extract_valid_mobile_phone(transcript)
        if phone is not None:
            return "phone_number", phone

        booking_match = _BOOKING_ID_LABEL_PATTERN.search(transcript)
        if booking_match is None:
            booking_match = _STANDALONE_BOOKING_ID_PATTERN.fullmatch(transcript.strip())
        if booking_match is not None:
            return "booking_id", booking_match.group("value")
        return None

    @staticmethod
    def _contextual_identifier(
        state: AgentState,
        data: TripLookupData,
    ) -> tuple[str, str] | None:
        if data.found_booking_id:
            return "booking_id", data.found_booking_id
        try:
            booking = BookingData.model_validate(state.collected_data.get("booking", {}))
        except ValueError:
            return None
        if booking.booking_id:
            return "booking_id", booking.booking_id
        return None

    @staticmethod
    def _matches(payload: LookupTripResult) -> list[TripMatch]:
        if payload.trips:
            return payload.trips
        assert payload.booking_id is not None
        return [
            TripMatch(
                booking_id=payload.booking_id,
                status=payload.status,
                eta_minutes=payload.eta_minutes,
            )
        ]

    @staticmethod
    def _trip_label(match: TripMatch, index: int) -> str:
        if match.pickup_label and match.destination_label:
            return f"từ {match.pickup_label} đến {match.destination_label}"
        if match.destination_label:
            return f"đến {match.destination_label}"
        return f"chuyến gần đây thứ {index}"

    @staticmethod
    def _match_trip(transcript: str, matches: list[TripMatch]) -> TripMatch | None:
        number = re.search(r"\b([1-9])\b", transcript)
        if number:
            index = int(number.group(1)) - 1
            if 0 <= index < len(matches):
                return matches[index]
        normalized = transcript.casefold()
        named = [
            match
            for match in matches
            if (match.pickup_label and match.pickup_label.casefold() in normalized)
            or (match.destination_label and match.destination_label.casefold() in normalized)
        ]
        return named[0] if len(named) == 1 else None

    @staticmethod
    def _status_label(status: str | None) -> str:
        if status is None:
            return "chưa có trạng thái mới"
        labels = {
            "CONFIRMED": "đã xác nhận",
            "DRIVER_EN_ROUTE": "tài xế đang đến điểm đón",
            "DRIVER_ARRIVED": "tài xế đã đến điểm đón",
            "IN_PROGRESS": "đang thực hiện",
            "COMPLETED": "đã hoàn thành",
            "CANCELLED": "đã hủy",
            "CANCELED": "đã hủy",
        }
        return labels.get(status.strip().upper(), status)

    @staticmethod
    def _understood_identifier(
        understanding: UnderstandingResult | None,
    ) -> tuple[str, str] | None:
        if understanding is None:
            return None
        if understanding.booking_id:
            return "booking_id", understanding.booking_id
        if understanding.phone_number:
            return "phone_number", understanding.phone_number
        return None
