"""Cache audio TTS cho câu tĩnh hay lặp lại — Phần 6 (Ref `S2-4`).

Giảm phụ thuộc gọi Edge-TTS mỗi lượt cho các câu không đổi (chào hỏi, xin
lỗi, câu handoff...) — cũng giảm bớt tác động nếu Edge-TTS tạm thời lỗi
(rủi ro đã ghi ở overview §9) cho đúng những câu đã cache sẵn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.voice.gateway import REPROMPT_MESSAGE

if TYPE_CHECKING:
    from src.voice.schemas import TTSResult
    from src.voice.tts.base import TTSProvider

# Câu tĩnh hay gặp — pre-render bằng CachingTTSProvider.prewarm() lúc khởi
# động app. Danh sách còn ngắn vì mới có gateway.py dùng câu re-prompt cố
# định; bổ sung thêm khi Phần 7 hoàn thiện kịch bản demo/handoff.
STATIC_PHRASES: list[str] = [
    REPROMPT_MESSAGE,
    "Xin chào, tôi có thể giúp gì cho bạn?",
    "Xin lỗi vì sự bất tiện này, tôi sẽ chuyển bạn sang tổng đài viên.",
]


class CachingTTSProvider:
    """Bọc quanh 1 `TTSProvider` bất kỳ — cache theo cặp (text, voice)."""

    def __init__(self, inner: TTSProvider) -> None:
        self._inner = inner
        self._cache: dict[tuple[str, str | None], TTSResult] = {}

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:
        key = (text, voice)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = await self._inner.synthesize(text, voice=voice)
        self._cache[key] = result
        return result

    async def prewarm(self, phrases: list[str] | None = None, *, voice: str | None = None) -> None:
        """Gọi lúc khởi động app — pre-render trước danh sách câu tĩnh."""
        for phrase in phrases if phrases is not None else STATIC_PHRASES:
            await self.synthesize(phrase, voice=voice)

    def cache_size(self) -> int:
        return len(self._cache)
