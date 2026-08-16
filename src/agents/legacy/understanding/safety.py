import re

from src.agents.core.booking_types import VehicleType
from src.agents.core.phone_policy import PHONE_CANDIDATE_PATTERN, normalize_phone
from src.agents.legacy.understanding.models import (
    ConfirmationIntent,
    CorrectionField,
    UnderstandingResult,
)

_PASSENGER_PATTERN = re.compile(
    r"\b(?P<count>\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*"
    r"(?:người|hành\s*khách)\b",
    re.IGNORECASE,
)
_LUGGAGE_PATTERN = re.compile(
    r"\b(?P<count>\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*"
    r"(?:vali|va\s*li|hành\s*lý)\b",
    re.IGNORECASE,
)
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

    if result.vehicle_type is not None and not _raw_contains_vehicle(
        normalized_raw,
        result.vehicle_type,
    ):
        updates["vehicle_type"] = None

    if result.passenger_count is not None and not _raw_contains_passenger_count(
        raw_transcript,
        result.passenger_count,
    ):
        updates["passenger_count"] = None
    if result.luggage_count is not None and not _raw_contains_count(
        raw_transcript,
        result.luggage_count,
        _LUGGAGE_PATTERN,
    ):
        updates["luggage_count"] = None
    if result.vehicle_preference and not _raw_contains_preference(
        normalized_raw,
        result.vehicle_preference,
    ):
        updates["vehicle_preference"] = None

    grounded_corrections = [
        correction
        for correction in result.corrections
        if _correction_has_raw_evidence(
            correction.field,
            correction.value,
            raw_transcript,
        )
    ]
    if len(grounded_corrections) != len(result.corrections):
        updates["corrections"] = grounded_corrections

    if result.selection is not None and not _raw_contains_selection(
        normalized_raw,
        result.selection.index,
    ):
        updates["selection"] = None

    return result.model_copy(update=updates, deep=True)


def _correction_has_raw_evidence(
    field: CorrectionField,
    value: str | None,
    raw_transcript: str,
) -> bool:
    if value is None:
        return True
    if field is CorrectionField.PHONE_NUMBER:
        return _raw_contains_phone(raw_transcript, value)
    if field is CorrectionField.VEHICLE_TYPE:
        return _raw_contains_vehicle_correction(raw_transcript.casefold(), value)
    return value.casefold() in raw_transcript.casefold()


def _raw_contains_phone(raw_transcript: str, value: str) -> bool:
    expected = _normalize_phone(value)
    return any(
        normalize_phone(match.group()) == expected
        for match in PHONE_CANDIDATE_PATTERN.finditer(raw_transcript)
    )


def _normalize_phone(value: str) -> str:
    return normalize_phone(value)


def _raw_contains_vehicle(raw_transcript: str, vehicle: VehicleType) -> bool:
    evidence = {
        VehicleType.MOTORBIKE: ("xe máy", "xe may"),
        VehicleType.CAR_4: ("4 chỗ", "bốn chỗ"),
        VehicleType.CAR_7: ("7 chỗ", "bảy chỗ"),
        VehicleType.LUXURY: ("cao cấp", "premium", "luxury"),
    }[vehicle]
    return any(term in raw_transcript for term in evidence)


def _raw_contains_vehicle_correction(raw_transcript: str, value: str | None) -> bool:
    if value is None:
        return True
    try:
        vehicle = VehicleType(value)
    except ValueError:
        return False
    return _raw_contains_vehicle(raw_transcript, vehicle)


def _raw_contains_passenger_count(raw_transcript: str, expected: int) -> bool:
    return _raw_contains_count(raw_transcript, expected, _PASSENGER_PATTERN)


def _raw_contains_count(
    raw_transcript: str,
    expected: int,
    pattern: re.Pattern[str],
) -> bool:
    match = pattern.search(raw_transcript)
    if match is None:
        return False
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
    actual = words.get(token, int(token) if token.isdigit() else None)
    return actual == expected


def _raw_contains_preference(raw_transcript: str, preference: str) -> bool:
    evidence = {
        "comfortable": ("thoải mái", "rộng", "rộng rãi"),
        "economical": ("rẻ", "tiết kiệm", "giá thấp"),
        "premium": ("cao cấp", "premium", "sang"),
    }.get(preference.casefold(), ())
    return any(term in raw_transcript for term in evidence)


def _raw_contains_selection(raw_transcript: str, index: int) -> bool:
    evidence = {
        1: ("1", "một", "đầu tiên", "thứ nhất"),
        2: ("2", "hai", "thứ hai"),
        3: ("3", "ba", "thứ ba"),
        4: ("4", "bốn", "thứ tư"),
        5: ("5", "năm", "thứ năm"),
        6: ("6", "sáu", "thứ sáu"),
        7: ("7", "bảy", "thứ bảy"),
        8: ("8", "tám", "thứ tám"),
        9: ("9", "chín", "thứ chín"),
    }[index]
    return any(re.search(rf"\b{re.escape(term)}\b", raw_transcript) for term in evidence)
