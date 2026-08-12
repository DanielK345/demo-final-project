"""ASR provider contract — sở hữu chính thức: Phần 3 (`docs/voice_ai_overview.md` §5).

Định nghĩa ở đây trước (Phần 1/2) chỉ để `gateway.py` có type để lập trình
theo và để CI có thể chạy end-to-end bằng fake provider ngay từ Tuần 1.
Phần 3 implement `groq_provider.py` theo đúng interface này — **không tự ý
đổi signature** (Definition of Done, overview §7); nếu cần đổi, bàn với
Phần 2 trước vì `gateway.py` gọi trực tiếp interface này.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.models.voice_schemas import ASRResult


@runtime_checkable
class ASRProvider(Protocol):
    """Nhận một utterance PCM16 16kHz mono đã cắt xong (do `EndpointScorer`
    xác định), trả về transcript + confidence.
    """

    async def transcribe(
        self,
        pcm16_audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "vi",
        prompt_hint: str = "",
    ) -> ASRResult:
        """`prompt_hint`: gợi ý địa danh từ gazetteer (Phần 4,
        `text/gazetteer.py::Gazetteer.as_prompt_hint()`) để bias nhận dạng —
        provider có thể bỏ qua nếu API không hỗ trợ prompt-conditioning.
        """
        ...
