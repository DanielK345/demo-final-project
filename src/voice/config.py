"""Settings riêng cho Voice AI — cố tình TÁCH khỏi `src/backend/config.py`.

Lý do tách: `src/backend/config.py` là `Settings` của team Backend, không có field
nào của Voice. Thêm field vào đó sẽ là sửa file người khác đang sở hữu — thay vào đó
Voice tự đọc `.env` (cùng file) qua class riêng, không đụng gì tới `Settings` của họ.
Xem `docs/voice-ai/voice-runtime-architecture.md` cho quyết định tích hợp đầy đủ.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
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

    # D2 — TTS (Edge-TTS). Keep this separate from Backend's VOICE_TTS_VOICE,
    # which contains OpenAI voice names such as "nova" and "alloy". Those are not
    # valid Edge-TTS voice IDs and otherwise fail at runtime in edge_tts.Communicate.
    voice_tts_voice: str = Field(
        default="vi-VN-HoaiMyNeural",
        validation_alias="VOICE_EDGE_TTS_VOICE",
    )
    # 1.0 = tốc độ gốc của giọng neural — nghe tự nhiên nhất. Bản trước đặt 0.9 (chậm
    # 10%, ý định "persona người lớn tuổi") nhưng làm giọng nghe robot/đơ hơn hẳn —
    # kéo chậm audio qua tham số rate của TTS engine (không phải resample) hay tạo méo
    # tiếng. Đổi lại 1.0 theo phản hồi thật; nếu vẫn cần giọng chậm cho người lớn tuổi,
    # nên test lại 0.95 trước, không nên xuống hẳn 0.9.
    voice_tts_rate: float = Field(default=1.0, gt=0.0, le=2.0)
    voice_tts_primary_voice: str = Field(
        default="vi-VN-HoaiMyNeural",
        validation_alias=AliasChoices("VOICE_TTS_PRIMARY_VOICE", "VOICE_TTS_VOICE"),
    )
    voice_tts_fallback_voices: str = "vi-VN-NamMinhNeural"
    voice_tts_timeout_seconds: float = Field(default=12.0, gt=0, le=60)
    voice_tts_request_deadline_seconds: float = Field(default=30.0, gt=0, le=180)
    voice_tts_max_attempts_per_voice: int = Field(default=2, ge=1, le=3)
    voice_tts_circuit_failure_threshold: int = Field(default=1, ge=1, le=20)
    voice_tts_circuit_cooldown_seconds: float = Field(default=60.0, gt=0, le=3600)
    voice_tts_max_concurrency: int = Field(default=4, ge=1, le=32)
    voice_tts_queue_size: int = Field(default=16, ge=1, le=256)
    voice_tts_max_text_chars: int = Field(default=2000, ge=1, le=10000)
    voice_tts_max_audio_bytes: int = Field(default=5_242_880, ge=1024, le=52_428_800)
    voice_tts_ffmpeg_path: str = "ffmpeg"
    voice_tts_ffprobe_path: str = "ffprobe"
    voice_tts_cache_max_entries: int = Field(default=64, ge=0, le=1000)
    voice_tts_cache_ttl_seconds: float = Field(default=900.0, gt=0, le=86400)
    voice_tts_cache_max_text_chars: int = Field(default=240, ge=0, le=2000)
    voice_browser_tts_fallback_enabled: bool = False

    @property
    def voice_tts_fallback_voice_list(self) -> list[str]:
        return [voice.strip() for voice in self.voice_tts_fallback_voices.split(",") if voice.strip()]

    # D3/D4 — VAD + endpoint detection
    voice_vad_backend: Literal["silero", "energy"] = "energy"
    voice_vad_silence_ms: int = Field(default=900, ge=100, le=5000)
    voice_vad_sample_rate: int = 16000
    voice_silero_model_path: str = ""
    voice_max_utterance_seconds: int = Field(default=30, ge=5)

    # Ngưỡng RMS tối thiểu của cả utterance trước khi tốn 1 lần gọi Groq API — chặn
    # hallucination khi audio gần như im lặng (phát hiện thật, xem mustdo.md).
    voice_min_utterance_rms: float = Field(default=0.01, ge=0.0, le=1.0)

    # Ngưỡng confidence RIÊNG của Voice — chỉ áp dụng thêm 1 lớp thận trọng phía client
    # khi đang ở bước CONFIRM (BR-001), KHÔNG thay thế ngưỡng 0.55 phẳng của
    # `SessionService` (nguồn quyết định duy nhất cho các bước còn lại).
    voice_booking_confirmation_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)


@lru_cache
def get_voice_settings() -> VoiceSettings:
    return VoiceSettings()
