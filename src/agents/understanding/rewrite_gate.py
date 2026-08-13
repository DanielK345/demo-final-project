import re

from src.agents.context import CandidateField, ConversationContext
from src.agents.state import ConversationRole, DeliveryStatus
from src.agents.understanding.rewrite_models import RewriteDecision, RewriteReason

_DEICTIC_PATTERN = re.compile(
    r"\b(?:ở\s+đó|chỗ\s+(?:đó|kia|này)|cái\s+(?:đó|kia|này)|nơi\s+đó)\b",
    re.IGNORECASE,
)
_PREVIOUS_TURN_PATTERN = re.compile(
    r"\b(?:lúc\s+nãy|vừa\s+rồi|ban\s+nãy|như\s+(?:trước|lúc\s+nãy))\b",
    re.IGNORECASE,
)
_AMBIGUOUS_CORRECTION_PATTERN = re.compile(
    r"\b(?:đổi|sửa|thay)\b.*\b(?:chỗ|điểm|cái|nơi)\s+(?:đó|kia|này)\b",
    re.IGNORECASE,
)
_DIGIT_SELECTION_PATTERN = re.compile(
    r"^(?:chọn\s+)?(?:cái\s+)?(?:số|thứ)\s*(?P<index>[1-9])(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_WORD_SELECTION_PATTERN = re.compile(
    r"^(?:chọn\s+)?(?:cái\s+)?thứ\s+"
    r"(?P<ordinal>nhất|một|hai|ba|bốn|tư|năm|sáu|bảy|tám|chín)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)

_ORDINAL_WORDS = {
    "nhất": 1,
    "một": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "tư": 4,
    "năm": 5,
    "sáu": 6,
    "bảy": 7,
    "tám": 8,
    "chín": 9,
}
_HANDOFF_TERMS = (
    "tổng đài viên",
    "người thật",
    "nhân viên hỗ trợ",
    "gặp nhân viên",
    "khiếu nại",
    "phàn nàn",
    "khẩn cấp",
    "nguy hiểm",
    "cứu tôi",
    "không cho tôi xuống xe",
    "tai nạn",
)
_EXPLICIT_CONFIRMATION_TERMS = (
    "đúng",
    "đồng ý",
    "xác nhận",
    "đặt đi",
    "đặt giúp",
    "chính xác",
    "vâng",
    "ừ",
)
_EXPLICIT_REJECTION_TERMS = (
    "không đồng ý",
    "không xác nhận",
    "không đặt",
    "sai rồi",
    "chưa đúng",
)
_EXPLICIT_REJECTION_UTTERANCES = {"không", "chưa"}
_SELF_CONTAINED_TERMS = (
    "đặt xe",
    "gọi xe",
    "tra cứu",
    "mã chuyến",
    "thanh toán",
    "chính sách",
)


class ContextualRewriteGate:
    """Deterministically decides whether contextual rewrite is worth attempting."""

    def __init__(self, *, max_short_reply_words: int = 4) -> None:
        if max_short_reply_words < 1:
            raise ValueError("max_short_reply_words must be positive")
        self.max_short_reply_words = max_short_reply_words

    def evaluate(
        self,
        raw_transcript: str,
        context: ConversationContext,
    ) -> RewriteDecision:
        normalized = " ".join(raw_transcript.casefold().split())
        if not normalized or self._must_use_fast_path(normalized):
            return RewriteDecision(should_rewrite=False)

        reasons: list[RewriteReason] = []
        candidate_index = _candidate_index(normalized)
        if (
            candidate_index is not None
            and context.last_assistant_message is not None
            and _candidate_group_size(context) >= candidate_index
        ):
            reasons.append(RewriteReason.ORDINAL_SELECTION)

        has_reference_context = _has_reference_context(context)
        if _AMBIGUOUS_CORRECTION_PATTERN.search(normalized) and has_reference_context:
            reasons.append(RewriteReason.AMBIGUOUS_CORRECTION)
        elif _DEICTIC_PATTERN.search(normalized) and has_reference_context:
            reasons.append(RewriteReason.DEICTIC_REFERENCE)

        if _PREVIOUS_TURN_PATTERN.search(normalized) and _has_previous_turn_context(context):
            reasons.append(RewriteReason.PREVIOUS_TURN_REFERENCE)

        if (
            len(normalized.split()) <= self.max_short_reply_words
            and context.last_assistant_message is not None
            and not reasons
            and candidate_index is None
            and not any(term in normalized for term in _SELF_CONTAINED_TERMS)
        ):
            reasons.append(RewriteReason.SHORT_CONTEXTUAL_REPLY)

        return RewriteDecision(
            should_rewrite=bool(reasons),
            reasons=reasons,
        )

    @staticmethod
    def _must_use_fast_path(normalized: str) -> bool:
        if any(term in normalized for term in _HANDOFF_TERMS):
            return True
        if any(term in normalized for term in _EXPLICIT_REJECTION_TERMS):
            return True
        if normalized.strip(" ,.!?") in _EXPLICIT_REJECTION_UTTERANCES:
            return True
        return any(re.match(rf"^{re.escape(term)}(?:\b|[,!.?])", normalized) for term in _EXPLICIT_CONFIRMATION_TERMS)


def _candidate_index(normalized: str) -> int | None:
    digit_match = _DIGIT_SELECTION_PATTERN.match(normalized)
    if digit_match is not None:
        return int(digit_match.group("index"))
    word_match = _WORD_SELECTION_PATTERN.match(normalized)
    if word_match is None:
        return None
    return _ORDINAL_WORDS[word_match.group("ordinal")]


def _candidate_group_size(context: ConversationContext) -> int:
    counts: dict[CandidateField, int] = {}
    for candidate in context.available_candidates:
        counts[candidate.field] = counts.get(candidate.field, 0) + 1
    if context.current_step == "SELECT_PICKUP_CANDIDATE":
        return counts.get(CandidateField.PICKUP, 0)
    if context.current_step == "SELECT_DESTINATION_CANDIDATE":
        return counts.get(CandidateField.DESTINATION, 0)
    return max(counts.values(), default=0)


def _has_reference_context(context: ConversationContext) -> bool:
    return bool(context.last_assistant_message or context.available_candidates or context.business_snapshot)


def _has_previous_turn_context(context: ConversationContext) -> bool:
    return bool(
        any(
            message.role is ConversationRole.USER
            or (
                message.role is ConversationRole.ASSISTANT
                and message.delivery_status in {DeliveryStatus.DELIVERED, DeliveryStatus.INTERRUPTED}
            )
            for message in context.recent_messages
        )
        or context.conversation_summary
        or context.business_snapshot
    )
