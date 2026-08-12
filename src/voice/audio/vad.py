"""Voice Activity Detection + endpointing — Phần 1 (`docs/voice_ai_overview.md` §4/§6).

Hai lớp trách nhiệm tách biệt:

- `VADProvider` (Protocol): "đoạn audio 20-30ms này có phải tiếng nói không?"
  Có 2 implementation: `EnergyVAD` (không phụ thuộc gì, dùng mặc định cho
  dev/test/CI) và `SileroVAD` (ONNX, chốt kỹ thuật D4 — dùng khi có model
  weight thật, xem `docs/mustdo_voice.md`).
- `EndpointScorer`: state machine "utterance đã nói xong chưa?" dựa trên
  ngưỡng im lặng cố định 900ms (D3). Không quan tâm VAD phía sau là gì.

`gateway.py` chỉ nói chuyện với `EndpointScorer`, không tự đọc frame VAD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np

from src.voice.audio.codec import pcm16_bytes_to_float32


class VADProvider(Protocol):
    def is_speech(self, frame: np.ndarray, sample_rate: int) -> float:
        """Trả về xác suất tiếng nói trong [0, 1] cho một frame audio float32."""
        ...


class EnergyVAD:
    """VAD dựa trên năng lượng (RMS) — 0 dependency, chạy được ở mọi nơi.

    Mặc định cho dev/test/CI (xem `voice_vad_backend=energy` trong
    `config.py`) và cho `FakeVADProvider`-style test. Không tốt bằng
    Silero khi có nhiễu nền, nhưng đủ để pipeline chạy end-to-end trước
    khi có model Silero thật.
    """

    def __init__(self, threshold_rms: float = 0.02) -> None:
        self.threshold_rms = threshold_rms

    def is_speech(self, frame: np.ndarray, sample_rate: int) -> float:  # noqa: ARG002
        if frame.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(frame))))
        return 1.0 if rms >= self.threshold_rms else 0.0


class SileroVAD:
    """Silero VAD (ONNX) — quyết định D4 đã chốt cho production.

    CHƯA test end-to-end trong môi trường này (không tải được model
    weight thật / không có `onnxruntime` cài sẵn) — xem
    `docs/mustdo_voice.md` mục Silero VAD trước khi bật
    `voice_vad_backend=silero`.

    Cách lấy model: tải `silero_vad.onnx` từ repo chính thức
    (https://github.com/snakers4/silero-vad, thư mục `files/`) rồi set
    `VOICE_SILERO_MODEL_PATH` trỏ tới file đó.
    """

    def __init__(self, model_path: str) -> None:
        if not model_path:
            raise ValueError(
                "SileroVAD cần voice_silero_model_path trỏ tới silero_vad.onnx "
                "(xem docs/mustdo_voice.md). Dùng backend='energy' nếu chưa có model."
            )
        try:
            import onnxruntime as ort  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise ImportError(
                "SileroVAD cần package 'onnxruntime'. Chạy `pip install onnxruntime` "
                "hoặc bỏ comment dòng onnxruntime trong requirements.txt."
            ) from exc

        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        input_names = {i.name for i in self._session.get_inputs()}
        # Silero VAD ONNX có 2 layout tuỳ version: v3/v4 dùng state "h"+"c",
        # v5 gộp thành 1 tensor "state". Tự nhận diện để không phải hardcode version.
        self._io_layout: Literal["state", "h_c"] = "state" if "state" in input_names else "h_c"
        self._h = None
        self._c = None
        self._state = None
        self.reset_state()

    def reset_state(self) -> None:
        if self._io_layout == "state":
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
        else:
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def is_speech(self, frame: np.ndarray, sample_rate: int) -> float:
        if frame.size == 0:
            return 0.0
        x = frame.reshape(1, -1).astype(np.float32)
        sr = np.array(sample_rate, dtype=np.int64)

        if self._io_layout == "state":
            ort_inputs = {"input": x, "state": self._state, "sr": sr}
            out, new_state = self._session.run(None, ort_inputs)
            self._state = new_state
        else:
            ort_inputs = {"input": x, "h": self._h, "c": self._c, "sr": sr}
            out, new_h, new_c = self._session.run(None, ort_inputs)
            self._h, self._c = new_h, new_c

        return float(np.asarray(out).reshape(-1)[0])


def build_vad_provider(
    backend: Literal["silero", "energy"],
    *,
    silero_model_path: str = "",
    energy_threshold_rms: float = 0.02,
) -> VADProvider:
    """Factory — `gateway.py`/tests dùng hàm này thay vì tự chọn class."""
    if backend == "silero":
        return SileroVAD(silero_model_path)
    return EnergyVAD(threshold_rms=energy_threshold_rms)


# ---------------------------------------------------------------------------
# Endpointing — D3: ngưỡng im lặng cố định 900ms
# ---------------------------------------------------------------------------

EndpointEvent = Literal["speech_start", "speech_end"]


@dataclass
class EndpointResult:
    event: EndpointEvent
    utterance_pcm16: bytes | None = None  # chỉ có giá trị khi event == "speech_end"
    utterance_ms: float = 0.0


@dataclass
class EndpointScorer:
    """Cắt audio streaming (16kHz mono PCM16) thành từng utterance.

    Sau khi resample (codec.py) về 16kHz, đẩy từng chunk vào `push()`.
    Khi phát hiện đủ 900ms im lặng sau khi đã có tiếng nói, trả về
    `EndpointResult(event="speech_end", utterance_pcm16=...)` chứa toàn bộ
    audio của utterance đó — sẵn sàng đưa cho ASR (Phần 3).
    """

    vad: VADProvider
    sample_rate: int = 16000
    frame_ms: int = 32
    silence_ms: int = 900
    speech_prob_threshold: float = 0.5
    max_utterance_ms: int = 30_000

    _buf: bytearray = field(default_factory=bytearray, init=False, repr=False)
    _speaking: bool = field(default=False, init=False, repr=False)
    _silence_ms_acc: float = field(default=0.0, init=False, repr=False)
    _frames: list[bytes] = field(default_factory=list, init=False, repr=False)
    _utterance_ms: float = field(default=0.0, init=False, repr=False)

    @property
    def frame_size(self) -> int:
        return max(1, int(self.sample_rate * self.frame_ms / 1000))

    def reset(self) -> None:
        self._buf = bytearray()
        self._speaking = False
        self._silence_ms_acc = 0.0
        self._frames = []
        self._utterance_ms = 0.0

    def push(self, pcm16_chunk: bytes) -> list[EndpointResult]:
        """Feed thêm audio 16kHz PCM16; trả về 0..n sự kiện phát hiện được."""
        self._buf.extend(pcm16_chunk)
        results: list[EndpointResult] = []
        frame_bytes_len = self.frame_size * 2  # PCM16 = 2 bytes/sample
        while len(self._buf) >= frame_bytes_len:
            frame = bytes(self._buf[:frame_bytes_len])
            del self._buf[:frame_bytes_len]
            results.extend(self._process_frame(frame))
        return results

    def flush(self) -> EndpointResult | None:
        """Kết thúc utterance đang dở (ví dụ user gác máy giữa chừng nói)."""
        if self._speaking and self._frames:
            return self._finish_utterance()
        self.reset()
        return None

    def _process_frame(self, frame: bytes) -> list[EndpointResult]:
        prob = self.vad.is_speech(pcm16_bytes_to_float32(frame), self.sample_rate)
        is_speech = prob >= self.speech_prob_threshold
        frame_ms = self.frame_size / self.sample_rate * 1000
        out: list[EndpointResult] = []

        if is_speech:
            if not self._speaking:
                self._speaking = True
                self._frames = []
                self._utterance_ms = 0.0
                out.append(EndpointResult(event="speech_start"))
            self._silence_ms_acc = 0.0
            self._frames.append(frame)
            self._utterance_ms += frame_ms
        elif self._speaking:
            self._silence_ms_acc += frame_ms
            self._frames.append(frame)  # giữ khoảng lặng ngắn để utterance nghe tự nhiên khi phát lại
            self._utterance_ms += frame_ms
            if self._silence_ms_acc >= self.silence_ms:
                out.append(self._finish_utterance())
                return out

        if self._speaking and self._utterance_ms >= self.max_utterance_ms:
            out.append(self._finish_utterance())

        return out

    def _finish_utterance(self) -> EndpointResult:
        pcm = b"".join(self._frames)
        utterance_ms = self._utterance_ms
        self._speaking = False
        self._silence_ms_acc = 0.0
        self._frames = []
        self._utterance_ms = 0.0
        return EndpointResult(event="speech_end", utterance_pcm16=pcm, utterance_ms=utterance_ms)
