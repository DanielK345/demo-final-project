"""TTS provider contract — sở hữu chính thức: Phần 5 (`docs/voice-ai/voice_ai_overview.md` §5).

Xem ghi chú ownership ở `src/voice/asr/base.py` — cùng lý do, cùng
nguyên tắc "không tự ý đổi signature".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.models.voice_schemas import TTSResult


@runtime_checkable
class TTSProvider(Protocol):
    """Tổng hợp giọng nói cho một câu trả lời (đã qua formatter/pronunciation
    ở Phần 6 — provider ở đây chỉ lo phần audio synthesis).
    """

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> TTSResult: ...
