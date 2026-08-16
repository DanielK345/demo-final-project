from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ZipformerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    asr_enabled: bool = True
    asr_required: bool = False
    asr_model_id: str = "hynt/Zipformer-30M-RNNT-6000h"
    asr_model_revision: str = "24ed30248e1c96bb690c81c24ab4e056f8cd9fce"
    asr_model_dir: Path = Path("data/models/asr/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
    asr_encoder_path: str = "encoder.int8.onnx"
    asr_decoder_path: str = "decoder.onnx"
    asr_joiner_path: str = "joiner.int8.onnx"
    asr_tokens_path: str = "tokens.txt"
    asr_num_threads: int = Field(default=2, ge=1, le=32)
    asr_max_concurrency: int = Field(default=2, ge=1, le=16)
    asr_queue_size: int = Field(default=8, ge=1, le=256)
    asr_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    asr_feature_dim: int = Field(default=80, ge=1, le=256)
    asr_inference_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    max_audio_size_mb: int = Field(default=15, ge=1, le=100)
    max_audio_duration_seconds: float = Field(default=60.0, gt=0, le=600)
    asr_ffmpeg_path: str = "ffmpeg"

    def model_path(self, filename: str) -> Path:
        path = Path(filename)
        return path if path.is_absolute() else self.asr_model_dir / path

    @property
    def required_model_files(self) -> dict[str, Path]:
        return {
            "encoder": self.model_path(self.asr_encoder_path),
            "decoder": self.model_path(self.asr_decoder_path),
            "joiner": self.model_path(self.asr_joiner_path),
            "tokens": self.model_path(self.asr_tokens_path),
        }


@lru_cache
def get_zipformer_settings() -> ZipformerSettings:
    return ZipformerSettings()
