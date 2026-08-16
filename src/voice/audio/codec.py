"""PCM16 codec helpers — Phần 1 (`docs/voice-ai/voice-runtime-architecture.md` §4, module `audio/codec.py`).

Trình duyệt gửi mic audio dạng PCM16 mono ở sample rate tuỳ thiết bị
(thường 48kHz, đôi khi 44.1/16kHz). VAD (Silero) và ASR (Groq Whisper)
đều cần 16kHz mono. Module này chỉ làm đúng một việc: resample PCM16
16-bit little-endian.

Không phụ thuộc gì ngoài `numpy` — không cần ffmpeg/libsox, chạy tốt
trên PaaS free tier.
"""

from __future__ import annotations

import numpy as np

PCM16_DTYPE = np.dtype("<i2")  # little-endian signed 16-bit, đúng format browser gửi lên


def pcm16_bytes_to_float32(chunk: bytes) -> np.ndarray:
    """PCM16 bytes -> float32 samples trong [-1.0, 1.0]. Dùng chung cho VAD/ASR."""
    if not chunk:
        return np.empty(0, dtype=np.float32)
    samples = np.frombuffer(chunk, dtype=PCM16_DTYPE)
    return (samples.astype(np.float32)) / 32768.0


def utterance_rms(pcm16_audio: bytes) -> float:
    """RMS (root-mean-square) của toàn bộ đoạn PCM16 — dùng làm "sanity check" ở
    tầng utterance (khác với `EnergyVAD`, vốn chỉ xét từng frame ~32ms). VAD có thể
    false-positive ngắt quãng khiến cả utterance thực chất gần như im lặng dù từng
    có vài frame vượt ngưỡng — `gateway.py` dùng hàm này trước khi gọi ASR để tránh
    tốn request cho audio rác (xem mustdo.md, mục hallucination khi im lặng).
    """
    samples = pcm16_bytes_to_float32(pcm16_audio)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def float32_to_pcm16_bytes(samples: np.ndarray) -> bytes:
    """Ngược lại của `pcm16_bytes_to_float32` — dùng khi cần trả PCM16 thô."""
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype(PCM16_DTYPE).tobytes()


def resample_pcm16(chunk: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample một đoạn PCM16 mono độc lập (không giữ state giữa các lần gọi).

    Dùng cho unit test hoặc khi xử lý file audio trọn vẹn. Khi xử lý audio
    streaming theo chunk nhỏ (WebSocket), dùng `PCM16Resampler` bên dưới để
    tránh click/artifact ở ranh giới giữa các chunk.
    """
    if src_rate == dst_rate or not chunk:
        return chunk
    samples = np.frombuffer(chunk, dtype=PCM16_DTYPE).astype(np.float32)
    if samples.size == 0:
        return b""
    if samples.size == 1:
        return samples.astype(PCM16_DTYPE).tobytes()

    duration = (samples.size - 1) / src_rate
    n_out = max(1, int(round(duration * dst_rate)) + 1)
    src_x = np.arange(samples.size, dtype=np.float64)
    dst_x = np.linspace(0, samples.size - 1, num=n_out, dtype=np.float64)
    resampled = np.interp(dst_x, src_x, samples)
    return resampled.astype(PCM16_DTYPE).tobytes()


class PCM16Resampler:
    """Resampler streaming, giữ 1 sample "carry" giữa các chunk để nội suy
    liên tục qua ranh giới chunk (tránh tiếng click nhỏ khi ghép các đoạn
    audio đã resample lại với nhau).

    Dùng 1 instance cho mỗi audio stream (mỗi `VoiceSession`); gọi
    `reset()` khi bắt đầu utterance mới hoặc đổi sample rate nguồn.
    """

    def __init__(self, target_rate: int = 16000) -> None:
        self.target_rate = target_rate
        self._src_rate: int | None = None
        self._carry: float | None = None  # sample cuối của chunk trước, theo float32
        self._next_pos: float = 0.0  # vị trí (đơn vị: sample nguồn) của output sample kế tiếp,
        # tính từ đầu chunk hiện tại (0 = sample đầu chunk hiện tại)

    def reset(self) -> None:
        self._carry = None
        self._next_pos = 0.0

    def process(self, chunk: bytes, src_rate: int) -> bytes:
        if src_rate != self._src_rate:
            self.reset()
            self._src_rate = src_rate

        if not chunk:
            return b""

        if src_rate == self.target_rate:
            # Passthrough, nhưng vẫn cập nhật carry để nếu rate đổi giữa chừng
            # (hiếm, nhưng có thể xảy ra nếu client đổi device) thì tiếp tục nội suy đúng.
            samples = np.frombuffer(chunk, dtype=PCM16_DTYPE)
            if samples.size:
                self._carry = float(samples[-1])
            return chunk

        samples = pcm16_bytes_to_float32(chunk)
        n = samples.size
        if n == 0:
            return b""

        step = src_rate / self.target_rate

        if self._carry is not None:
            x_known = np.arange(-1, n, dtype=np.float64)
            y_known = np.concatenate(([self._carry], samples))
        else:
            x_known = np.arange(0, n, dtype=np.float64)
            y_known = samples
            if self._next_pos < 0:
                self._next_pos = 0.0

        out_positions = []
        pos = self._next_pos
        while pos <= n - 1:
            out_positions.append(pos)
            pos += step

        if out_positions:
            out_x = np.array(out_positions, dtype=np.float64)
            out_samples = np.interp(out_x, x_known, y_known).astype(np.float32)
            out_bytes = float32_to_pcm16_bytes(out_samples)
        else:
            out_bytes = b""

        self._next_pos = pos - n  # dịch mốc tham chiếu cho chunk kế tiếp
        self._carry = float(samples[-1])
        return out_bytes
