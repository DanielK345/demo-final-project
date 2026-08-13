import re

from src.agents.understanding.models import ConfirmationIntent, UnderstandingResult

_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
_RAW_CONFIRMATION_TERMS = (
    "đúng",
    "đồng ý",
    "xác nhận",
    "đặt đi",
    "đặt giúp",
    "chính xác",
    "vâng",
)
_RAW_REJECTION_TERMS = ("không", "chưa", "hủy", "sai")


def enforce_raw_understanding_evidence(
    result: UnderstandingResult,
    *,
    raw_transcript: str,
) -> UnderstandingResult:
    """Remove critical facts that are not supported by the raw user utterance."""
    updates: dict[str, object] = {}
    normalized_raw = raw_transcript.casefold()
    raw_confirms = any(term in normalized_raw for term in _RAW_CONFIRMATION_TERMS)
    raw_rejects = any(term in normalized_raw for term in _RAW_REJECTION_TERMS)

    if result.confirmation is ConfirmationIntent.CONFIRM and (not raw_confirms or raw_rejects):
        updates["confirmation"] = ConfirmationIntent.UNCLEAR

    if result.phone_number and not _raw_contains_phone(
        raw_transcript,
        result.phone_number,
    ):
        updates["phone_number"] = None

    if result.booking_id and result.booking_id.casefold() not in normalized_raw:
        updates["booking_id"] = None

    return result.model_copy(update=updates, deep=True)


def _raw_contains_phone(raw_transcript: str, value: str) -> bool:
    expected = _normalize_phone(value)
    return any(_normalize_phone(match.group()) == expected for match in _PHONE_PATTERN.finditer(raw_transcript))


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("84"):
        return f"0{digits[2:]}"
    return digits
