import re

from src.agents.understanding.models import (
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
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
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


class RuleBasedUnderstanding:
    _BOOKING_TERMS = ("đặt xe", "gọi xe", "book", "ride")
    _LOOKUP_TERMS = ("tra cứu", "mã chuyến", "chuyến của tôi", "eta")
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
        del context
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
        phone_match = _PHONE_PATTERN.search(transcript)
        booking_match = _BOOKING_ID_PATTERN.search(transcript)
        corrections: list[Correction] = []
        pickup_correction = _PICKUP_CORRECTION.search(transcript)
        destination_correction = _DESTINATION_CORRECTION.search(transcript)
        phone_correction = _PHONE_CORRECTION.search(transcript)
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

        confirmation = ConfirmationIntent.NOT_APPLICABLE
        if any(term in normalized for term in self._REJECT_TERMS):
            confirmation = ConfirmationIntent.REJECT
        elif any(term in normalized for term in self._CONFIRM_TERMS):
            confirmation = ConfirmationIntent.CONFIRM

        return UnderstandingResult(
            intent=intent,
            pickup_query=(route.group("pickup").strip(" .") if route else None),
            destination_query=(
                route.group("destination").strip(" .") if route else None
            ),
            phone_number=(
                self._normalize_phone(phone_match.group()) if phone_match else None
            ),
            booking_id=(booking_match.group("value") if booking_match else None),
            confirmation=confirmation,
            corrections=corrections,
            confidence=1.0 if intent is not UnderstandingIntent.UNKNOWN else 0.0,
        )

    @staticmethod
    def _normalize_phone(value: str) -> str:
        phone = re.sub(r"\D", "", value)
        return f"0{phone[2:]}" if phone.startswith("84") else phone
