import re

from src.agents.core.booking_types import VehicleType
from src.agents.core.phone_policy import extract_valid_mobile_phone
from src.agents.legacy.understanding.models import (
    ConfirmationIntent,
    CorrectionField,
    UnderstandingResult,
)

_ROUTE_PATTERN = re.compile(
    r"\btừ\s+(?P<pickup>.+?)\s+(?:đến|tới|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_PASSENGER_PATTERN = re.compile(
    r"\b(?P<count>\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*"
    r"(?:người|hành\s*khách)\b",
    re.IGNORECASE,
)
_PICKUP_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?đón"
    r"(?:\s+(?:sang|thành|là))?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_DESTINATION_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:điểm\s+)?(?:đến|đích)"
    r"(?:\s+(?:sang|thành|là))?\s+(?P<value>.+)",
    re.IGNORECASE,
)
_PHONE_CORRECTION = re.compile(
    r"(?:(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:số\s+)?điện\s+thoại"
    r"(?:\s+(?:sang|thành|là))?|(?:số\s+)?điện\s+thoại\s+(?:đúng\s+)?là)"
    r"\s+(?P<value>(?:\+?84|0)(?:[ .-]?\d){9})",
    re.IGNORECASE,
)
_VEHICLE_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay)\s+(?:lại\s+)?(?:loại\s+)?xe(?:\s+(?:sang|thành|là))?"
    r"\s+(?P<value>xe\s+máy|(?:ô\s*tô\s*)?[47]\s*chỗ)",
    re.IGNORECASE,
)
_PASSENGER_CORRECTION = re.compile(
    r"(?:đổi|sửa|thay|thực\s+ra)(?:\s+lại)?(?:\s+(?:số\s+)?(?:người|hành\s*khách))?"
    r"(?:\s+(?:sang|thành|là|có))?\s+"
    r"(?P<value>(?:\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)"
    r"\s*(?:người|hành\s*khách))",
    re.IGNORECASE,
)
_PICKUP_FIELD = re.compile(r"\b(?:điểm\s+)?đón\b", re.IGNORECASE)
_DESTINATION_FIELD = re.compile(r"\b(?:điểm\s+)?(?:đến|đích)\b", re.IGNORECASE)
_PHONE_FIELD = re.compile(r"\b(?:số\s+)?điện\s+thoại\b", re.IGNORECASE)
_VEHICLE_FIELD = re.compile(r"\b(?:loại\s+xe|xe\s+máy|[47]\s*chỗ)\b", re.IGNORECASE)
_PASSENGER_FIELD = re.compile(r"\b(?:(?:số\s+)?người|hành\s*khách)\b", re.IGNORECASE)
_GENERIC_CORRECTION = re.compile(
    r"\b(?:tôi\s+muốn\s+)?sửa(?:\s+lại)?\s+thông\s+tin\b",
    re.IGNORECASE,
)
_CONFIRM_PATTERN = re.compile(
    r"^(?:(?:vâng|ừ|đúng|đồng\s+ý|xác\s+nhận)(?:\s+rồi)?"
    r"(?:[, ]+(?:đặt(?:\s+xe)?(?:\s+giúp(?:\s+tôi|\s+bác)?)?(?:\s+đi)?).*)?"
    r"|đặt(?:\s+xe)?(?:\s+giúp(?:\s+tôi|\s+bác)?)?(?:\s+đi)?)$",
    re.IGNORECASE,
)
_REJECT_PATTERN = re.compile(
    r"^(?:không|chưa|không\s+đồng\s+ý|không\s+xác\s+nhận|chưa\s+đúng|sai\s+rồi)"
    r"(?:[,.! ]|$)",
    re.IGNORECASE,
)

_NUMBER_WORDS = {
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


def extract_route(transcript: str) -> tuple[str, str] | None:
    match = _ROUTE_PATTERN.search(transcript)
    if match is None:
        return None
    return match.group("pickup").strip(" ."), match.group("destination")


def extract_phone(transcript: str) -> str | None:
    return extract_valid_mobile_phone(transcript)


def extract_vehicle(value: str) -> VehicleType | None:
    normalized = " ".join(value.casefold().split())
    serialized = {
        VehicleType.MOTORBIKE.value.casefold(): VehicleType.MOTORBIKE,
        VehicleType.CAR_4.value.casefold(): VehicleType.CAR_4,
        VehicleType.CAR_7.value.casefold(): VehicleType.CAR_7,
    }
    if normalized in serialized:
        return serialized[normalized]
    if "xe máy" in normalized or "xe may" in normalized:
        return VehicleType.MOTORBIKE
    if re.search(r"\b(?:4|bốn)\s*chỗ\b", normalized):
        return VehicleType.CAR_4
    if re.search(r"\b(?:7|bảy)\s*chỗ\b", normalized):
        return VehicleType.CAR_7
    return None


def extract_passenger_count(value: str) -> int | None:
    match = _PASSENGER_PATTERN.search(value)
    if match is None:
        return None
    return _parse_number(match.group("count"))


def parse_passenger_count(value: str) -> int | None:
    extracted = extract_passenger_count(value)
    if extracted is not None:
        return extracted
    normalized = value.casefold().strip(" .,;!?")
    number = _parse_number(normalized)
    return number if number is not None and 1 <= number <= 50 else None


def extract_correction(transcript: str) -> tuple[CorrectionField, str | None] | None:
    patterns = (
        (CorrectionField.PICKUP, _PICKUP_CORRECTION),
        (CorrectionField.DESTINATION, _DESTINATION_CORRECTION),
        (CorrectionField.PHONE_NUMBER, _PHONE_CORRECTION),
        (CorrectionField.PASSENGER_COUNT, _PASSENGER_CORRECTION),
    )
    for field, pattern in patterns:
        match = pattern.search(transcript)
        if match is not None:
            return field, match.group("value").strip(" .")

    vehicle = _VEHICLE_CORRECTION.search(transcript)
    if vehicle is not None:
        parsed = extract_vehicle(vehicle.group("value"))
        return CorrectionField.VEHICLE_TYPE, parsed.value if parsed else None

    normalized = transcript.casefold()
    if any(term in normalized for term in ("đổi", "sửa", "thay")):
        field = select_correction_field(transcript)
        if field is not None:
            return field, None
    return None


def understood_correction(
    understanding: UnderstandingResult | None,
) -> tuple[CorrectionField, str | None] | None:
    if understanding is None or not understanding.corrections:
        return None
    correction = understanding.corrections[0]
    return correction.field, correction.value


def select_correction_field(transcript: str) -> CorrectionField | None:
    for field, pattern in (
        (CorrectionField.PICKUP, _PICKUP_FIELD),
        (CorrectionField.DESTINATION, _DESTINATION_FIELD),
        (CorrectionField.PHONE_NUMBER, _PHONE_FIELD),
        (CorrectionField.VEHICLE_TYPE, _VEHICLE_FIELD),
        (CorrectionField.PASSENGER_COUNT, _PASSENGER_FIELD),
    ):
        if pattern.search(transcript):
            return field
    return None


def is_generic_correction(transcript: str) -> bool:
    return _GENERIC_CORRECTION.search(transcript) is not None


def confirmation_intent(
    transcript: str,
    understanding: UnderstandingResult | None = None,
) -> ConfirmationIntent:
    if understanding is not None and understanding.confirmation in {
        ConfirmationIntent.CONFIRM,
        ConfirmationIntent.REJECT,
    }:
        return understanding.confirmation
    normalized = transcript.casefold().strip(" .!?")
    if _REJECT_PATTERN.match(normalized):
        return ConfirmationIntent.REJECT
    if _CONFIRM_PATTERN.fullmatch(normalized):
        return ConfirmationIntent.CONFIRM
    return ConfirmationIntent.UNCLEAR


def _parse_number(value: str) -> int | None:
    normalized = value.casefold()
    if normalized in _NUMBER_WORDS:
        return _NUMBER_WORDS[normalized]
    return int(normalized) if normalized.isdigit() else None
