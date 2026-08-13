"""Edge-TTS provider — Phần 5, D2 (`docs/voice_ai_overview.md`).

Edge-TTS gọi API không chính thức của Microsoft (qua package `edge-tts`,
kết nối WebSocket tới `speech.platform.bing.com`) — rủi ro đã ghi trong
overview §9 (có thể bị chặn/đổi API bất kỳ lúc nào). Đã tự verify gọi được
thật (miễn phí, không cần key) trong phiên phát triển này — vẫn nên coi là
"best-effort", không phải SLA đảm bảo; `tts/cache.py` (Phần 6) giảm bớt phụ
thuộc bằng cách pre-render câu tĩnh hay dùng.
"""

from __future__ import annotations

import logging
from typing import Protocol

import edge_tts

from src.models.voice_schemas import TTSResult

logger = logging.getLogger(__name__)

_MP3_SAMPLE_RATE = 24000  # edge-tts mặc định xuất mp3 ~24kHz


class _CommunicateFactory(Protocol):
    def __call__(self, text: str, voice: str, *, rate: str) -> edge_tts.Communicate: ...


def rate_to_edge_tts_param(rate: float) -> str:
    """`rate`: 1.0 = tốc độ bình thường (cùng đơn vị với `voice_tts_rate` trong
    `config.py`, vd 0.9). edge-tts nhận chuỗi phần trăm thay đổi so với tốc độ
    gốc (vd "-10%")."""
    percent = round((rate - 1.0) * 100)
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent}%"


class EdgeTTSProvider:
    """Implement `TTSProvider` (`voice/tts/base.py`) bằng Edge-TTS."""

    def __init__(
        self,
        *,
        default_voice: str = "vi-VN-HoaiMyNeural",
        rate: float = 1.0,
        communicate_factory: _CommunicateFactory | None = None,
    ) -> None:
        self._default_voice = default_voice
        self._rate_param = rate_to_edge_tts_param(rate)
        # inject factory trong test — không tạo kết nối mạng thật trong CI.
        self._communicate_factory: _CommunicateFactory = communicate_factory or edge_tts.Communicate

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:
        if not text.strip():
            return TTSResult(audio=b"", text=text)

        communicate = self._communicate_factory(text, voice or self._default_voice, rate=self._rate_param)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])

        return TTSResult(
            audio=b"".join(chunks),
            mime_type="audio/mpeg",
            sample_rate=_MP3_SAMPLE_RATE,
            text=text,
        )
