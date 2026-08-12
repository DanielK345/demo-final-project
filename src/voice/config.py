"""Settings riêng cho Voice AI — cố tình TÁCH khỏi `src/backend/config.py`.

Lý do tách: `src/backend/config.py` là `Settings` của team Backend, không có field
nào của Voice. Thêm field vào đó sẽ là sửa file người khác đang sở hữu — thay vào đó
Voice tự đọc `.env` (cùng file) qua class riêng, không đụng gì tới `Settings` của họ.
Xem `docs/prompt_voice_integration_real_be_fe.md` cho quyết định tích hợp đầy đủ.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    voice_enabled: bool = True

    # D1 — ASR (Groq Whisper)
    groq_api_key: str = ""
    voice_asr_model: str = "whisper-large-v3-turbo"
    voice_asr_language: str = "vi"

    # D2 — TTS (Edge-TTS)
    voice_tts_voice: str = "vi-VN-HoaiMyNeural"
    # 1.0 = tốc độ gốc của giọng neural — nghe tự nhiên nhất. Bản trước đặt 0.9 (chậm
    # 10%, ý định "persona người lớn tuổi") nhưng làm giọng nghe robot/đơ hơn hẳn —
    # kéo chậm audio qua tham số rate của TTS engine (không phải resample) hay tạo méo
    # tiếng. Đổi lại 1.0 theo phản hồi thật; nếu vẫn cần giọng chậm cho người lớn tuổi,
    # nên test lại 0.95 trước, không nên xuống hẳn 0.9.
    voice_tts_rate: float = Field(default=1.0, gt=0.0, le=2.0)

    # D3/D4 — VAD + endpoint detection
    voice_vad_backend: Literal["silero", "energy"] = "energy"
    voice_vad_silence_ms: int = Field(default=900, ge=100, le=5000)
    voice_vad_sample_rate: int = 16000
    voice_silero_model_path: str = ""
    voice_max_utterance_seconds: int = Field(default=30, ge=5)

    # Ngưỡng RMS tối thiểu của cả utterance trước khi tốn 1 lần gọi Groq API — chặn
    # hallucination khi audio gần như im lặng (phát hiện thật, xem docs/mustdo_voice.md).
    voice_min_utterance_rms: float = Field(default=0.01, ge=0.0, le=1.0)

    # Ngưỡng confidence RIÊNG của Voice — chỉ áp dụng thêm 1 lớp thận trọng phía client
    # khi đang ở bước CONFIRM (BR-001), KHÔNG thay thế ngưỡng 0.55 phẳng của
    # `SessionService` (nguồn quyết định duy nhất cho các bước còn lại).
    voice_booking_confirmation_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)


@lru_cache
def get_voice_settings() -> VoiceSettings:
    return VoiceSettings()
