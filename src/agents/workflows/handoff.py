from enum import StrEnum
from typing import Any

from src.agents.guardrails import redact_pii
from src.agents.policy import AgentPolicy
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.understanding.models import UnderstandingIntent, UnderstandingResult
from src.agents.workflows.base import BaseWorkflow


class HandoffReason(StrEnum):
    USER_REQUEST = "USER_REQUEST"
    COMPLAINT = "COMPLAINT"
    EMERGENCY = "EMERGENCY"
    RETRY_LIMIT = "RETRY_LIMIT"
    CRITICAL_TOOL_ERROR = "CRITICAL_TOOL_ERROR"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNABLE_TO_CONTINUE = "UNABLE_TO_CONTINUE"


class HandoffWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.HUMAN_HANDOFF
    context_key = "handoff_context"

    _USER_REQUEST_TERMS = (
        "tổng đài viên",
        "người thật",
        "nhân viên hỗ trợ",
        "gặp nhân viên",
    )
    _COMPLAINT_TERMS = (
        "khiếu nại",
        "phàn nàn",
        "tài xế thái độ",
        "tài xế không phù hợp",
    )
    _EMERGENCY_TERMS = (
        "khẩn cấp",
        "nguy hiểm",
        "cứu tôi",
        "không cho tôi xuống xe",
        "tai nạn",
    )

    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> AgentAction:
        if agent_input.session_id != state.session_id:
            raise ValueError("agent input and state must belong to the same session")

        handoff_reason = self.detect_reason(agent_input, state, understanding)
        context = self.build_context(agent_input, state, handoff_reason)
        collected_data = {
            key: value
            for key, value in state.collected_data.items()
            if key != self.context_key
        }
        collected_data[self.context_key] = context

        return AgentAction(
            action_type=ActionType.HANDOFF,
            message="Tôi sẽ chuyển bạn tới tổng đài viên.",
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "HANDOFF_REQUESTED",
                "collected_data": collected_data,
                "pending_tool_call_id": None,
                "pending_tool_name": None,
            },
            reason=f"Human handoff required: {handoff_reason.value}.",
        )

    def detect_reason(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> HandoffReason:
        transcript = agent_input.transcript.casefold().strip()

        if any(term in transcript for term in self._EMERGENCY_TERMS):
            return HandoffReason.EMERGENCY
        if any(term in transcript for term in self._COMPLAINT_TERMS):
            return HandoffReason.COMPLAINT
        if any(term in transcript for term in self._USER_REQUEST_TERMS):
            return HandoffReason.USER_REQUEST
        if (
            understanding is not None
            and understanding.intent is UnderstandingIntent.HUMAN_HANDOFF
        ):
            return HandoffReason.USER_REQUEST
        if (
            agent_input.tool_result is not None
            and agent_input.tool_result.status is ToolStatus.ERROR
        ):
            return HandoffReason.CRITICAL_TOOL_ERROR
        if state.retry_count >= self.policy.max_retry_count:
            return HandoffReason.RETRY_LIMIT
        if (
            agent_input.stt_confidence is not None
            and agent_input.stt_confidence < self.policy.low_confidence_threshold
        ):
            return HandoffReason.LOW_CONFIDENCE
        return HandoffReason.UNABLE_TO_CONTINUE

    def build_context(
        self,
        agent_input: AgentInput,
        state: AgentState,
        handoff_reason: HandoffReason,
    ) -> dict[str, Any]:
        business_data = {
            key: value
            for key, value in state.collected_data.items()
            if key != self.context_key
        }
        context: dict[str, Any] = {
            "session_id": state.session_id,
            "reason_code": handoff_reason.value,
            "summary": self._build_summary(agent_input, state, handoff_reason),
            "source_workflow": (
                state.current_workflow.value
                if state.current_workflow is not None
                else None
            ),
            "source_step": state.current_step,
            "retry_count": state.retry_count,
            "stt_confidence": agent_input.stt_confidence,
            "business_data": business_data,
        }

        if agent_input.tool_result is not None:
            context["tool_result"] = {
                "tool_name": agent_input.tool_result.tool_name.value,
                "call_id": agent_input.tool_result.call_id,
                "status": agent_input.tool_result.status.value,
                "error": agent_input.tool_result.error,
            }

        return context

    @staticmethod
    def _build_summary(
        agent_input: AgentInput,
        state: AgentState,
        handoff_reason: HandoffReason,
    ) -> str:
        transcript = redact_pii(" ".join(agent_input.transcript.split())) or ""
        if len(transcript) > 300:
            transcript = f"{transcript[:297]}..."

        source = (
            state.current_workflow.value
            if state.current_workflow is not None
            else "NO_ACTIVE_WORKFLOW"
        )
        user_text = transcript or "No user transcript was provided."
        return (
            f"Reason={handoff_reason.value}; workflow={source}; "
            f"step={state.current_step or 'UNKNOWN'}; user={user_text}"
        )
