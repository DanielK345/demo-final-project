from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class OutputDecision(StrEnum):
    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"
    HANDOFF = "HANDOFF"


class TTSOutputReviewDecision(BaseModel):
    decision: OutputDecision
    approved_text: str
    reason_codes: list[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    reviewer_version: str = "deterministic-v1"


_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)]\((?:https?://|www\.)[^)]+\)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+?84)|0)\d{9}(?!\d)")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_JSON_OUTPUT_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)
_SECRET_RE = re.compile(
    r"(?:sk-(?:or-)?[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._-]{16,}|api[_ -]?key\s*[:=])",
    re.IGNORECASE,
)
_INTERNAL_RE = re.compile(
    r"(?:traceback \(most recent call last\)|system prompt|tool_call|stack trace|database password)",
    re.IGNORECASE,
)
_BOOKING_SUCCESS_RE = re.compile(
    r"(?:đặt xe|chuyến xe).{0,80}(?:thành công|đã được xác nhận)", re.IGNORECASE
)
_ABSOLUTE_PROMISE_RE = re.compile(
    r"\b(?:chắc chắn|cam kết)\s+(?:hoàn tiền|bồi thường|được hoàn|được bồi thường)\b",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _mask_phone(match: re.Match[str]) -> str:
    number = match.group(0)
    return f"số điện thoại kết thúc bằng {number[-3:]}"


class DeterministicTTSOutputReviewer:
    def __init__(self, *, max_chars: int = 2000) -> None:
        self.max_chars = max_chars

    def review(self, text: str, *, context: dict[str, Any] | None = None) -> TTSOutputReviewDecision:
        original = text.strip()
        if not original:
            return TTSOutputReviewDecision(
                decision=OutputDecision.BLOCK,
                approved_text="",
                reason_codes=["EMPTY_OUTPUT"],
                risk_level="MEDIUM",
            )
        if _JSON_OUTPUT_RE.match(original):
            return TTSOutputReviewDecision(
                decision=OutputDecision.HANDOFF,
                approved_text="Xin lỗi, nội dung phản hồi chưa đúng định dạng để đọc thành tiếng.",
                reason_codes=["INTERNAL_STRUCTURED_OUTPUT"],
                risk_level="HIGH",
            )
        if _BOOKING_SUCCESS_RE.search(original) and not bool((context or {}).get("booking_confirmed")):
            return TTSOutputReviewDecision(
                decision=OutputDecision.HANDOFF,
                approved_text=(
                    "Tôi đã ghi nhận yêu cầu đặt xe nhưng chưa thể xác nhận chuyến xe thành công. "
                    "Vui lòng kiểm tra trạng thái trên màn hình hoặc chờ tổng đài viên hỗ trợ."
                ),
                reason_codes=["UNVERIFIED_BOOKING_CLAIM"],
                risk_level="HIGH",
            )
        if _SECRET_RE.search(original) or _INTERNAL_RE.search(original):
            return TTSOutputReviewDecision(
                decision=OutputDecision.HANDOFF,
                approved_text="Xin lỗi, nội dung này cần được tổng đài viên kiểm tra trước khi trả lời.",
                reason_codes=["INTERNAL_OR_SECRET_CONTENT"],
                risk_level="HIGH",
            )

        reasons: list[str] = []
        reviewed = _CONTROL_RE.sub(" ", original)
        reviewed = _CODE_FENCE_RE.sub(" ", reviewed)
        reviewed = _MARKDOWN_LINK_RE.sub(r"\1", reviewed)
        if _URL_RE.search(reviewed):
            reviewed = _URL_RE.sub("đường dẫn đã được gửi trên màn hình", reviewed)
            reasons.append("URL_REMOVED")
        if _PHONE_RE.search(reviewed):
            reviewed = _PHONE_RE.sub(_mask_phone, reviewed)
            reasons.append("PHONE_MASKED")
        if _EMAIL_RE.search(reviewed):
            reviewed = _EMAIL_RE.sub("địa chỉ email đã được ẩn", reviewed)
            reasons.append("EMAIL_MASKED")
        if _ABSOLUTE_PROMISE_RE.search(reviewed):
            reviewed = _ABSOLUTE_PROMISE_RE.sub("đã ghi nhận yêu cầu về", reviewed)
            reasons.append("UNVERIFIED_PROMISE_REWRITTEN")
        reviewed = _WHITESPACE_RE.sub(" ", reviewed).strip()
        if len(reviewed) > self.max_chars:
            reviewed = reviewed[: self.max_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
            reasons.append("OUTPUT_TRUNCATED")

        return TTSOutputReviewDecision(
            decision=OutputDecision.REWRITE if reviewed != original else OutputDecision.ALLOW,
            approved_text=reviewed,
            reason_codes=reasons,
            risk_level="MEDIUM" if reasons else "LOW",
        )

