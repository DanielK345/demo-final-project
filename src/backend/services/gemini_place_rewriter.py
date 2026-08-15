"""Correct Vietnamese place names in an ASR transcript before Agent routing.

This is deliberately a narrow rewrite layer: it must not infer intent, add
addresses, alter confirmations, or change anything except a likely misspelled
place name. If Gemini is unavailable, the original transcript is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os

import httpx

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptRewriteResult:
    original: str
    rewritten: str
    applied: bool
    provider: str


class GeminiPlaceRewriter:
    _ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    _PROMPT = """Bạn là lớp hậu xử lý ASR tiếng Việt cho ứng dụng đặt xe.
Chỉ sửa tên địa danh có khả năng bị ASR nghe sai, dựa trên ngữ cảnh câu nói.
Ví dụ: "Bình Yuni" có thể là "VinUni"; "Hồ Cương" có thể là "Hồ Gươm".
Không thêm, xóa, diễn giải hay thay đổi bất kỳ phần nào khác của câu.
Nếu không chắc chắn, giữ nguyên. Chỉ trả về một câu transcript đã sửa, không có
nhãn, dấu ngoặc kép, giải thích hay Markdown.

Transcript: {transcript}"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def rewrite(self, transcript: str, *, source: str) -> TranscriptRewriteResult:
        original = transcript.strip()
        if source != "VOICE" or not original:
            return TranscriptRewriteResult(original, original, False, "skipped")
        # Unit tests must remain hermetic even when a developer has credentials
        # in their local .env file.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return TranscriptRewriteResult(original, original, False, "test")
        if not self.settings.asr_place_rewrite_enabled or not self.settings.google_api_key:
            return TranscriptRewriteResult(original, original, False, "disabled")

        payload = {
            "contents": [{"parts": [{"text": self._PROMPT.format(transcript=original)}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.asr_place_rewrite_timeout_seconds) as client:
                response = await client.post(
                    self._ENDPOINT.format(model=self.settings.asr_place_rewrite_model),
                    params={"key": self.settings.google_api_key},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            rewritten = str(body["candidates"][0]["content"]["parts"][0]["text"]).strip()
            # Guardrail: an empty/model-commentary response must never replace ASR text.
            if not rewritten or "\n" in rewritten:
                raise ValueError("Gemini returned an invalid rewrite")
            return TranscriptRewriteResult(original, rewritten, rewritten != original, "gemini")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Gemini ASR place rewrite failed; using original transcript: %s", exc)
            return TranscriptRewriteResult(original, original, False, "fallback")
