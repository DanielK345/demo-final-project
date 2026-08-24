import re

from src.agents.legacy.context_models import ConversationContext
from src.agents.legacy.understanding.rewrite_base import UnsafeRewriteOutputError
from src.agents.legacy.understanding.rewrite_models import RewriteDecision, RewriteResult

_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
_BOOKING_ID_PATTERN = re.compile(
    r"\b(?:GSM|BOOKING)[-_][A-Za-z0-9_-]{3,}\b",
    re.IGNORECASE,
)
_ADDRESS_PATTERN = re.compile(
    r"\b(?:\d+[A-Za-z]?\s+(?:đường|phố)\s+[\wÀ-ỹ.-]+|(?:quận|huyện)\s+[\wÀ-ỹ.-]+)",
    re.IGNORECASE,
)
_CONFIRMATION_TERMS = (
    "đồng ý",
    "xác nhận",
    "đặt xe đi",
    "đặt giúp",
    "chính xác",
)


def contains_sensitive_identity(value: str) -> bool:
    return bool(_PHONE_PATTERN.search(value) or _BOOKING_ID_PATTERN.search(value))


def validate_rewrite_result(
    result: RewriteResult,
    *,
    original_text: str,
    context: ConversationContext,
    decision: RewriteDecision,
) -> RewriteResult:
    if not decision.should_rewrite:
        raise UnsafeRewriteOutputError("rewrite was attempted after a fast-path decision")
    if result.original_text != original_text:
        raise UnsafeRewriteOutputError("rewrite changed the auditable original text")
    if not result.changed:
        return result.model_copy(deep=True)
    if not result.resolved_references:
        raise UnsafeRewriteOutputError("changed rewrite requires grounded reference evidence")

    source_turn_ids = {message.turn_id for message in context.recent_messages}
    if context.conversation_summary is not None:
        source_turn_ids.add(context.conversation_summary.summarized_through_turn_id)

    evidence_values = _evidence_values(context)
    normalized_original = original_text.casefold()
    normalized_rewrite = result.rewritten_text.casefold()
    for reference in result.resolved_references:
        if reference.source_turn_id not in source_turn_ids:
            raise UnsafeRewriteOutputError("resolved reference cites an unknown source turn")
        if reference.original_phrase.casefold() not in normalized_original:
            raise UnsafeRewriteOutputError("resolved phrase is not present in original text")
        if reference.resolved_value.casefold() not in normalized_rewrite:
            raise UnsafeRewriteOutputError("resolved value is not present in rewritten text")
        if not _is_reference_grounded(
            reference.resolved_value,
            reference.source_turn_id,
            context,
        ):
            raise UnsafeRewriteOutputError("resolved value is not grounded in context")

    _reject_new_matches(
        pattern=_PHONE_PATTERN,
        original_text=original_text,
        rewritten_text=result.rewritten_text,
        label="phone number",
    )
    _reject_new_matches(
        pattern=_BOOKING_ID_PATTERN,
        original_text=original_text,
        rewritten_text=result.rewritten_text,
        label="booking identity",
    )
    _reject_new_matches(
        pattern=_ADDRESS_PATTERN,
        original_text=original_text,
        rewritten_text=result.rewritten_text,
        label="address",
        grounded_values=evidence_values,
    )

    if not _contains_confirmation(original_text) and _contains_confirmation(result.rewritten_text):
        raise UnsafeRewriteOutputError("rewrite introduced booking confirmation")
    return result.model_copy(deep=True)


def _evidence_values(context: ConversationContext) -> list[str]:
    values = [field.value for field in context.business_snapshot]
    for candidate in context.available_candidates:
        values.append(candidate.display_name)
        if candidate.address:
            values.append(candidate.address)
    values.extend(message.content for message in context.recent_messages)
    if context.conversation_summary is not None:
        values.append(context.conversation_summary.content)
    return values


def _is_grounded(value: str, evidence_values: list[str]) -> bool:
    normalized = value.casefold().strip()
    return any(normalized in evidence.casefold() for evidence in evidence_values)


def _is_reference_grounded(
    value: str,
    source_turn_id: str,
    context: ConversationContext,
) -> bool:
    normalized = value.casefold().strip()
    source_messages = [message.content for message in context.recent_messages if message.turn_id == source_turn_id]
    if any(normalized in message.casefold() for message in source_messages):
        return True

    summary = context.conversation_summary
    if (
        summary is not None
        and summary.summarized_through_turn_id == source_turn_id
        and normalized in summary.content.casefold()
    ):
        return True

    last_assistant = context.last_assistant_message
    if last_assistant is None or last_assistant.turn_id != source_turn_id:
        return False
    candidate_values = [
        value
        for candidate in context.available_candidates
        for value in (candidate.display_name, candidate.address)
        if value
    ]
    return any(normalized == candidate.casefold().strip() for candidate in candidate_values)


def _reject_new_matches(
    *,
    pattern: re.Pattern[str],
    original_text: str,
    rewritten_text: str,
    label: str,
    grounded_values: list[str] | None = None,
) -> None:
    original_matches = {_normalize_match(match) for match in pattern.findall(original_text)}
    for match in pattern.findall(rewritten_text):
        normalized = _normalize_match(match)
        if normalized in original_matches:
            continue
        if grounded_values and _is_grounded(match, grounded_values):
            continue
        raise UnsafeRewriteOutputError(f"rewrite introduced an ungrounded {label}")


def _normalize_match(value: str) -> str:
    return re.sub(r"[ .-]", "", value).casefold()


def _contains_confirmation(value: str) -> bool:
    normalized = value.casefold()
    return any(term in normalized for term in _CONFIRMATION_TERMS)
