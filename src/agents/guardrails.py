import re

from pydantic import ValidationError

from src.agents.policy import AgentPolicy
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.tools.lifecycle import clear_pending_tool_updates

_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
_AGENT_MANAGED_STATE_FIELDS = {"conversation_history", "conversation_summary"}
_SIDE_EFFECT_TOOLS = {ToolName.CREATE_BOOKING, ToolName.CREATE_HANDOFF}


class GuardrailViolationError(ValueError):
    pass


class AgentGuardrails:
    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    def validate_and_sanitize(
        self,
        agent_input: AgentInput,
        state: AgentState,
        action: AgentAction,
    ) -> AgentAction:
        updates = dict(action.state_updates)
        managed_updates = _AGENT_MANAGED_STATE_FIELDS.intersection(updates)
        if managed_updates:
            fields = ", ".join(sorted(managed_updates))
            raise GuardrailViolationError(f"workflow cannot modify agent-managed state fields: {fields}")
        if agent_input.stt_confidence is not None:
            updates["last_stt_confidence"] = agent_input.stt_confidence

        try:
            next_state = state.apply(updates)
        except (ValidationError, ValueError) as exc:
            raise GuardrailViolationError("action contains invalid state updates") from exc

        if action.message and len(action.message) > self.policy.max_spoken_message_characters:
            raise GuardrailViolationError("spoken message exceeds the configured limit")

        if (
            state.pending_tool_name in _SIDE_EFFECT_TOOLS
            and agent_input.tool_result is None
            and (
                next_state.pending_tool_call_id != state.pending_tool_call_id
                or next_state.pending_tool_name is not state.pending_tool_name
            )
        ):
            raise GuardrailViolationError(
                "cannot clear an unresolved side effect without its tool result"
            )

        if (
            action.action_type is ActionType.END_SESSION
            and next_state.pending_tool_name in _SIDE_EFFECT_TOOLS
        ):
            raise GuardrailViolationError(
                "cannot end a session while a side effect requires reconciliation"
            )

        if next_state.current_step == "RECONCILIATION_REQUIRED":
            if action.action_type is not ActionType.HANDOFF:
                raise GuardrailViolationError("reconciliation requires a handoff action")
            if next_state.pending_tool_name not in _SIDE_EFFECT_TOOLS:
                raise GuardrailViolationError(
                    "reconciliation requires a pending side effect"
                )

        if action.action_type is ActionType.CALL_TOOL:
            assert action.tool_call is not None
            if next_state.pending_tool_call_id != action.tool_call.call_id:
                raise GuardrailViolationError("tool call is not registered as pending")
            if next_state.pending_tool_name is not action.tool_call.tool_name:
                raise GuardrailViolationError("pending tool name does not match the action")
            if (
                action.tool_call.tool_name is ToolName.CREATE_BOOKING
                and next_state.confirmation is not ConfirmationStatus.CONFIRMED
            ):
                raise GuardrailViolationError("create_booking requires explicit confirmed state")

        return action.model_copy(
            update={
                "state_updates": updates,
                "reason": redact_pii(action.reason),
            },
            deep=True,
        )

    @staticmethod
    def safe_handoff(reason: str) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message=("Tôi chưa thể tiếp tục xử lý tự động. Tôi sẽ chuyển bạn tới tổng đài viên."),
            state_updates={
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "HANDOFF_REQUIRED",
                **clear_pending_tool_updates(),
            },
            reason=redact_pii(reason),
        )

    @staticmethod
    def safe_reconciliation_handoff(reason: str) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message=(
                "Tôi cần kiểm tra trạng thái yêu cầu đang xử lý và sẽ chuyển "
                "bạn tới tổng đài viên."
            ),
            state_updates={
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "RECONCILIATION_REQUIRED",
            },
            reason=redact_pii(reason),
        )


def redact_pii(value: str | None) -> str | None:
    if value is None:
        return None
    return _PHONE_PATTERN.sub("[REDACTED_PHONE]", value)
