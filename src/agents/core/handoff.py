"""Deterministic human-handoff policy and typed operational context."""

from __future__ import annotations

from enum import StrEnum
from unicodedata import category, normalize

from src.agents.contracts.schemas import ActionType, AgentAction, WorkflowType
from src.agents.contracts.state import AgentState
from src.agents.core.guardrails import redact_pii


class HandoffReason(StrEnum):
    USER_REQUEST = "USER_REQUEST"
    EMERGENCY = "EMERGENCY"
    SAFETY_RISK = "SAFETY_RISK"
    COMPLAINT = "COMPLAINT"
    PAYMENT_DISPUTE = "PAYMENT_DISPUTE"
    LOST_ITEM = "LOST_ITEM"
    LOW_STT_CONFIDENCE = "LOW_STT_CONFIDENCE"
    RETRY_LIMIT = "RETRY_LIMIT"
    CRITICAL_TOOL_ERROR = "CRITICAL_TOOL_ERROR"
    SIDE_EFFECT_RECONCILIATION = "SIDE_EFFECT_RECONCILIATION"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    POLICY_BLOCK = "POLICY_BLOCK"
    UNABLE_TO_CONTINUE = "UNABLE_TO_CONTINUE"


class HandoffSeverity(StrEnum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_EMERGENCY_TERMS = (
    "cap cuu", "tai nan", "bi thuong", "nguy hiem", "de doa", "cuop",
    "hanh hung", "quay roi", "tai xe say", "khong an toan",
)
_SAFETY_TERMS = ("so tai xe", "lai xe nguy hiem", "bi theo doi", "mac ket trong xe")
_PAYMENT_TERMS = ("tru tien sai", "thu tien sai", "thu them tien", "tranh chap thanh toan")
_LOST_ITEM_TERMS = ("quen do", "mat do", "de quen", "that lac")
_COMPLAINT_TERMS = ("khieu nai", "phan nan", "to cao", "khong hai long")
_HUMAN_TERMS = (
    "tong dai vien", "nhan vien ho tro", "nguoi that", "gap nhan vien",
    "chuyen nhan vien", "noi chuyen voi nhan vien",
)


def classify_handoff(transcript: str) -> HandoffReason | None:
    """Return only high-confidence, realtime handoff intents.

    The model still handles semantic ambiguity; this function is the safety net
    that prevents urgent/user-requested transfers from depending on an LLM call.
    """

    text = normalize_text(transcript)
    if not text:
        return None
    for reason, terms in (
        (HandoffReason.SAFETY_RISK, _SAFETY_TERMS),
        (HandoffReason.EMERGENCY, _EMERGENCY_TERMS),
        (HandoffReason.PAYMENT_DISPUTE, _PAYMENT_TERMS),
        (HandoffReason.LOST_ITEM, _LOST_ITEM_TERMS),
        (HandoffReason.COMPLAINT, _COMPLAINT_TERMS),
        (HandoffReason.USER_REQUEST, _HUMAN_TERMS),
    ):
        if any(term in text for term in terms):
            return reason
    return None


def handoff_metadata(reason_code: HandoffReason) -> tuple[int, HandoffSeverity, str]:
    if reason_code is HandoffReason.EMERGENCY:
        return 100, HandoffSeverity.CRITICAL, "SAFETY_OPERATOR"
    if reason_code is HandoffReason.SAFETY_RISK:
        return 90, HandoffSeverity.CRITICAL, "SAFETY_OPERATOR"
    if reason_code in {HandoffReason.PAYMENT_DISPUTE, HandoffReason.LOST_ITEM}:
        return 75, HandoffSeverity.HIGH, "SPECIALIST_OPERATOR"
    if reason_code is HandoffReason.COMPLAINT:
        return 70, HandoffSeverity.HIGH, "CUSTOMER_CARE_OPERATOR"
    if reason_code is HandoffReason.SIDE_EFFECT_RECONCILIATION:
        return 85, HandoffSeverity.HIGH, "OPERATIONS_OPERATOR"
    return 50, HandoffSeverity.NORMAL, "GENERAL_OPERATOR"


def build_handoff_context(
    state: AgentState,
    *,
    reason_code: HandoffReason,
    reason: str,
) -> dict[str, object]:
    priority, severity, queue = handoff_metadata(reason_code)
    history = state.conversation_history[-6:]
    summary = " | ".join(f"{item.role.value}: {item.content}" for item in history)
    return {
        "reason_code": reason_code.value,
        "reason": redact_pii(reason) or reason_code.value,
        "priority": priority,
        "severity": severity.value,
        "queue": queue,
        "source_workflow": state.current_workflow.value if state.current_workflow else None,
        "summary": redact_pii(summary) or "No prior conversation summary.",
        "pending_tool": state.pending_tool_name.value if state.pending_tool_name else None,
        "requires_immediate_transfer": severity is HandoffSeverity.CRITICAL,
    }


def deterministic_handoff_action(
    state: AgentState,
    *,
    reason_code: HandoffReason,
    reason: str,
    state_updates: dict[str, object] | None = None,
) -> AgentAction:
    updates = dict(state_updates or {})
    collected = dict(updates.get("collected_data", state.collected_data))
    collected["handoff"] = build_handoff_context(state, reason_code=reason_code, reason=reason)
    severity = handoff_metadata(reason_code)[1]
    message = (
        "Tình huống này cần được ưu tiên ngay. Tôi sẽ chuyển bạn tới bộ phận hỗ trợ an toàn. "
        "Nếu đang nguy hiểm trực tiếp, hãy gọi số khẩn cấp tại nơi bạn đang ở."
        if severity is HandoffSeverity.CRITICAL
        else "Tôi sẽ chuyển bạn tới tổng đài viên và gửi kèm nội dung đã trao đổi."
    )
    return AgentAction(
        action_type=ActionType.HANDOFF,
        message=message,
        state_updates={
            **updates,
            "collected_data": collected,
            "current_workflow": WorkflowType.HUMAN_HANDOFF,
            "current_step": "HANDOFF_REQUIRED",
        },
        reason=redact_pii(reason),
    )


def normalize_text(value: str) -> str:
    decomposed = normalize("NFD", value.strip().casefold()).replace("đ", "d")
    without_marks = "".join(ch for ch in decomposed if category(ch) != "Mn")
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in without_marks).split())
