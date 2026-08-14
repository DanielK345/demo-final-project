"""Fake ASR/TTS providers — sở hữu chính thức: Phần 8 (`docs/voice-ai/voice_ai_overview.md` §5).

Tạo sớm ở đây (Tuần 1, theo lịch trình §8) để:

- CI không bao giờ gọi Groq/Edge-TTS thật (nguyên tắc test-double, §7).
- `gateway.py` (Phần 2) chạy và test được end-to-end trước khi Phần 3/5
  có provider thật.
- `api/voice_routes.py` dùng làm default provider cho demo khi chưa cấu
  hình `GROQ_API_KEY` (xem `docs/voice-ai/mustdo_voice.md`).

Phần 8 mở rộng thêm khi cần kịch bản test phức tạp hơn (lỗi, timeout,
độ trễ giả lập...) — không đổi tên 2 class này vì `voice_routes.py` và
test của Phần 1/2 import trực tiếp.
"""

from __future__ import annotations

from collections.abc import Callable

from src.voice.schemas import ASRResult, TTSResult


class FakeASRProvider:
    """Không gọi API thật. Trả kết quả từ hàng đợi `responses`, hoặc nếu
    hết hàng đợi thì trả transcript giả dựa trên độ dài audio nhận được —
    đủ để demo pipeline chạy hết vòng đời một lượt gọi mà không cần Groq.
    """

    def __init__(
        self,
        responses: list[ASRResult] | None = None,
        default_confidence: float = 0.95,
    ) -> None:
        self._queue = list(responses) if responses else None
        self.default_confidence = default_confidence
        self.calls: list[bytes] = []

    async def transcribe(
        self,
        pcm16_audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "vi",  # noqa: ARG002
        prompt_hint: str = "",  # noqa: ARG002
    ) -> ASRResult:
        self.calls.append(pcm16_audio)
        if self._queue:
            return self._queue.pop(0)
        duration_ms = int(len(pcm16_audio) / 2 / sample_rate * 1000) if sample_rate else 0
        return ASRResult(
            text=f"[demo] đã nhận {duration_ms}ms audio",
            confidence=self.default_confidence,
            duration_ms=duration_ms,
        )


class FakeTTSProvider:
    """Không gọi Edge-TTS thật. Trả audio giả (bytes UTF-8 của text theo
    mặc định) — đủ để test/route kiểm tra được đúng text đã được "nói".
    """

    def __init__(self, audio_factory: Callable[[str], bytes] | None = None) -> None:
        self._audio_factory = audio_factory or (lambda text: text.encode("utf-8"))
        self.calls: list[str] = []

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:  # noqa: ARG002
        self.calls.append(text)
        return TTSResult(
            audio=self._audio_factory(text),
            mime_type="audio/x-fake",
            sample_rate=16000,
            text=text,
        )


class FailingASRProvider:
    """Giả lập ASR provider lỗi (Groq sập/timeout...) — dùng test resilience
    của `gateway.py` (try/except quanh `self.asr.transcribe`, xem
    `docs/voice-ai/mustdo_voice.md`)."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("ASR provider tạm thời lỗi")
        self.calls = 0

    async def transcribe(
        self,
        pcm16_audio: bytes,  # noqa: ARG002
        *,
        sample_rate: int = 16000,  # noqa: ARG002
        language: str = "vi",  # noqa: ARG002
        prompt_hint: str = "",  # noqa: ARG002
    ) -> ASRResult:
        self.calls += 1
        raise self._exc


class FailingTTSProvider:
    """Giả lập TTS provider lỗi (Edge-TTS sập/timeout...) — dùng test
    resilience của `gateway.py` (try/except quanh `self.tts.synthesize`)."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("TTS provider tạm thời lỗi")
        self.calls = 0

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:  # noqa: ARG002
        self.calls += 1
        raise self._exc
