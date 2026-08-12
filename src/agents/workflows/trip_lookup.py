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
from src.agents.state import AgentState
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    clear_pending_tool_updates,
    correlate_tool_result,
    normalize_tool_failure,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.schemas import LookupTripResult
from src.agents.tools.trip import LookupTripTool
from src.agents.understanding.models import UnderstandingResult
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.handoff import HandoffWorkflow
from src.agents.workflows.trip_lookup_models import TripLookupData, TripLookupStep

_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
_BOOKING_ID_LABEL_PATTERN = re.compile(
    r"(?:mã\s+(?:chuyến|đặt\s*xe)|booking(?:\s*id)?)\s*(?:là|:|#)?\s*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9_-]{2,})",
    re.IGNORECASE,
)
_STANDALONE_BOOKING_ID_PATTERN = re.compile(
    r"^(?P<value>(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9][A-Za-z0-9_-]{3,})$"
)


class TripLookupWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.TRIP_LOOKUP
    data_key = "trip_lookup"
    max_retry_count = 3

    def __init__(self, lookup_tool: LookupTripTool | None = None) -> None:
        self.lookup_tool = lookup_tool or LookupTripTool()

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
            **pending_tool_updates(
                tool_call,
                waiting_step=TripLookupStep.WAITING_FOR_TRIP_RESULT.value,
            ),
        }
        if retry_count is not None:
            updates["retry_count"] = retry_count
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
            if failure.retryable and next_retry < self.max_retry_count:
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
                message=(
                    "Tôi chưa tìm thấy chuyến phù hợp. "
                    "Bạn vui lòng kiểm tra lại mã chuyến hoặc số điện thoại."
                ),
                state_updates={
                    "current_workflow": self.workflow_type,
                    "current_step": TripLookupStep.COLLECT_IDENTIFIER.value,
                    "collected_data": self._store_data(state, data),
                    "retry_count": state.retry_count + 1,
                    **clear_pending_tool_updates(),
                },
                reason="No trip matched the supplied identifier.",
            )

        data.found_booking_id = payload.booking_id
        data.trip_status = payload.status
        data.eta_minutes = payload.eta_minutes
        eta_message = (
            f" Thời gian dự kiến là {payload.eta_minutes} phút."
            if payload.eta_minutes is not None
            else ""
        )
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=f"Trạng thái chuyến hiện tại là {payload.status}.{eta_message}",
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                "retry_count": 0,
                **clear_pending_tool_updates(),
            },
            reason="Trip status and ETA came from the validated tool result.",
        )

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
        return TripLookupData.model_validate(
            state.collected_data.get(self.data_key, {})
        )

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
        phone_match = _PHONE_PATTERN.search(transcript)
        if phone_match is not None:
            phone = re.sub(r"\D", "", phone_match.group())
            if phone.startswith("84"):
                phone = f"0{phone[2:]}"
            return "phone_number", phone

        booking_match = _BOOKING_ID_LABEL_PATTERN.search(transcript)
        if booking_match is None:
            booking_match = _STANDALONE_BOOKING_ID_PATTERN.fullmatch(
                transcript.strip()
            )
        if booking_match is not None:
            return "booking_id", booking_match.group("value")
        return None

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
