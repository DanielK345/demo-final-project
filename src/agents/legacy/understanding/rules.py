import re

from src.agents.core.phone_policy import extract_valid_mobile_phone, normalize_phone
from src.agents.legacy.understanding.booking import extract_passenger_count, extract_vehicle
from src.agents.legacy.understanding.models import (
    BookingSelection,
    BookingSelectionTarget,
    ConfirmationIntent,
    Correction,
    CorrectionField,
    UnderstandingContext,
    UnderstandingIntent,
    UnderstandingResult,
)

_ROUTE_PATTERN = re.compile(
    r"\btừ\s+(?P<pickup>.+?)\s+(?:đến|tới|về)\s+(?P<destination>.+)$",
    re.IGNORECASE,
)
_BOOKING_ID_PATTERN = re.compile(
    r"(?:mã\s+(?:chuyến|đặt\s*xe)|booking(?:\s*id)?)\s*(?:là|:|#)?\s*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9_-]{2,})",
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
_LUGGAGE_PATTERN = re.compile(
    r"\b(?P<count>\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*"
    r"(?:vali|va\s*li|hành\s*lý)\b",
    re.IGNORECASE,
)
_SELECTION_PATTERN = re.compile(r"\b(?P<index>[1-9])\b")
_SELECTION_STEPS = {
    "SELECT_PICKUP_CANDIDATE": BookingSelectionTarget.PICKUP,
    "SELECT_DESTINATION_CANDIDATE": BookingSelectionTarget.DESTINATION,
    "SELECT_VEHICLE_OPTION": BookingSelectionTarget.VEHICLE,
}
_GENERIC_CORRECTION = re.compile(
    r"\b(?:đổi|sửa|thay)(?:\s+lại)?(?:\s+thông\s+tin)?\b",
    re.IGNORECASE,
)
_CORRECTION_FIELDS = (
    (CorrectionField.PICKUP, re.compile(r"\b(?:điểm\s+)?đón\b", re.IGNORECASE)),
    (
        CorrectionField.DESTINATION,
        re.compile(r"\b(?:điểm\s+)?(?:đến|đích)\b", re.IGNORECASE),
    ),
    (
        CorrectionField.PHONE_NUMBER,
        re.compile(r"\b(?:số\s+)?điện\s+thoại\b", re.IGNORECASE),
    ),
    (
        CorrectionField.VEHICLE_TYPE,
        re.compile(r"\b(?:loại\s+)?xe\b", re.IGNORECASE),
    ),
    (
        CorrectionField.PASSENGER_COUNT,
        re.compile(r"\b(?:(?:số\s+)?người|hành\s*khách)\b", re.IGNORECASE),
    ),
)


class RuleBasedUnderstanding:
    _BOOKING_TERMS = ("đặt xe", "gọi xe", "book", "ride")
    _LOOKUP_TERMS = (
        "tra cứu",
        "mã chuyến",
        "chuyến của tôi",
        "xe của tôi",
        "xe tới đâu",
        "xe đến đâu",
        "còn bao lâu",
        "tài xế tới đâu",
        "eta",
    )
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
    _FAQ_TERMS = ("dịch vụ", "giá", "thanh toán", "chính sách", "hoạt động")
    _CONFIRM_TERMS = ("đúng", "đồng ý", "xác nhận", "đặt đi", "đặt giúp")
    _REJECT_TERMS = ("không", "chưa", "hủy", "sai rồi")

    async def understand(
        self,
        transcript: str,
        context: UnderstandingContext,
    ) -> UnderstandingResult:
        normalized = transcript.casefold().strip()
        intent = UnderstandingIntent.UNKNOWN
        if any(term in normalized for term in self._HANDOFF_TERMS):
            intent = UnderstandingIntent.HUMAN_HANDOFF
        elif any(term in normalized for term in self._BOOKING_TERMS):
            intent = UnderstandingIntent.RIDE_BOOKING
        elif any(term in normalized for term in self._LOOKUP_TERMS):
            intent = UnderstandingIntent.TRIP_LOOKUP
        elif any(term in normalized for term in self._FAQ_TERMS):
            intent = UnderstandingIntent.FAQ

        route = _ROUTE_PATTERN.search(transcript)
        phone_number = extract_valid_mobile_phone(transcript)
        booking_match = _BOOKING_ID_PATTERN.search(transcript)
        corrections: list[Correction] = []
        pickup_correction = _PICKUP_CORRECTION.search(transcript)
        destination_correction = _DESTINATION_CORRECTION.search(transcript)
        phone_correction = _PHONE_CORRECTION.search(transcript)
        vehicle_correction = _VEHICLE_CORRECTION.search(transcript)
        selection_match = _SELECTION_PATTERN.search(transcript)
        selection_target = _SELECTION_STEPS.get(context.current_step or "")
        if pickup_correction is not None:
            corrections.append(
                Correction(
                    field=CorrectionField.PICKUP,
                    value=pickup_correction.group("value").strip(" ."),
                )
            )
        if destination_correction is not None:
            corrections.append(
                Correction(
                    field=CorrectionField.DESTINATION,
                    value=destination_correction.group("value").strip(" ."),
                )
            )
        if phone_correction is not None:
            corrections.append(
                Correction(
                    field=CorrectionField.PHONE_NUMBER,
                    value=self._normalize_phone(phone_correction.group("value")),
                )
            )
        if vehicle_correction is not None:
            vehicle = extract_vehicle(vehicle_correction.group("value"))
            assert vehicle is not None
            corrections.append(
                Correction(
                    field=CorrectionField.VEHICLE_TYPE,
                    value=vehicle.value,
                )
            )

        correction_requested = _GENERIC_CORRECTION.search(transcript) is not None
        if correction_requested and not corrections:
            field = next(
                (
                    candidate
                    for candidate, pattern in _CORRECTION_FIELDS
                    if pattern.search(transcript)
                ),
                None,
            )
            if field is not None:
                corrections.append(Correction(field=field))
        if context.current_step == "SELECT_CORRECTION_FIELD" and not corrections:
            field = next(
                (
                    candidate
                    for candidate, pattern in _CORRECTION_FIELDS
                    if pattern.search(transcript)
                ),
                None,
            )
            if field is not None:
                corrections.append(Correction(field=field))

        confirmation = ConfirmationIntent.NOT_APPLICABLE
        if any(normalized.startswith(term) for term in self._REJECT_TERMS):
            confirmation = ConfirmationIntent.REJECT
        elif any(term in normalized for term in self._CONFIRM_TERMS):
            confirmation = ConfirmationIntent.CONFIRM

        pickup_query = route.group("pickup").strip(" .") if route else None
        destination_query = (
            self._clean_destination_query(route.group("destination"))
            if route
            else None
        )
        if (
            route is None
            and confirmation is ConfirmationIntent.NOT_APPLICABLE
            and not correction_requested
            and self._looks_like_location_answer(normalized)
        ):
            if context.current_step in {
                "COLLECT_PICKUP",
                "WAITING_FOR_PICKUP_RESULT",
            }:
                pickup_query = transcript.strip(" .")
            elif context.current_step in {
                "COLLECT_DESTINATION",
                "WAITING_FOR_DESTINATION_RESULT",
            }:
                destination_query = transcript.strip(" .")

        return UnderstandingResult(
            intent=intent,
            pickup_query=pickup_query,
            destination_query=destination_query,
            phone_number=(
                phone_number
            ),
            vehicle_type=extract_vehicle(transcript),
            passenger_count=extract_passenger_count(transcript),
            luggage_count=self._extract_count(transcript, _LUGGAGE_PATTERN),
            vehicle_preference=self._extract_vehicle_preference(transcript),
            booking_id=(booking_match.group("value") if booking_match else None),
            confirmation=confirmation,
            correction_requested=correction_requested,
            corrections=corrections,
            selection=(
                BookingSelection(
                    target=selection_target,
                    index=int(selection_match.group("index")),
                )
                if selection_match is not None and selection_target is not None
                else None
            ),
            confidence=1.0 if intent is not UnderstandingIntent.UNKNOWN else 0.0,
        )

    @staticmethod
    def _normalize_phone(value: str) -> str:
        return normalize_phone(value)

    @staticmethod
    def _extract_count(value: str, pattern: re.Pattern[str]) -> int | None:
        match = pattern.search(value)
        if match is None:
            return None
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
        return words.get(token, int(token) if token.isdigit() else None)

    @staticmethod
    def _extract_vehicle_preference(value: str) -> str | None:
        normalized = value.casefold()
        if any(term in normalized for term in ("thoải mái", "rộng", "rộng rãi")):
            return "comfortable"
        if any(term in normalized for term in ("rẻ", "tiết kiệm", "giá thấp")):
            return "economical"
        if any(term in normalized for term in ("cao cấp", "premium", "sang trọng")):
            return "premium"
        return None

    @staticmethod
    def _clean_destination_query(value: str) -> str:
        cleaned = value.strip(" .,;")
        cleaned = re.sub(
            r"[,;]?\s+(?:cho\s+)?(?:\d{1,2}|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)"
            r"\s*(?:người|hành\s*khách)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[,;]?\s*(?:(?:đi|bằng|với)\s+)?"
            r"(?:xe\s+máy|xe\s+may|(?:ô\s*tô|xe)?\s*[47]\s*chỗ)"
            r"(?:\s+(?:giúp\s+tôi|nhé|ạ))?$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip(" .,;")

    @classmethod
    def _looks_like_location_answer(cls, normalized: str) -> bool:
        if not normalized or len(normalized) < 2:
            return False
        conversational_only = {
            "xin chào",
            "chào bạn",
            "cảm ơn",
            "tôi muốn đặt xe",
            "đặt xe",
            "gọi xe",
        }
        return normalized.strip(" .!?") not in conversational_only
