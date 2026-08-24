"""Configuration for the standalone ASR streaming server."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ASRServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    asr_server_host: str = "0.0.0.0"
    asr_server_port: int = 9000
    cors_origins_raw: str = "http://localhost:5173,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    # Model
    asr_model_id: str = "hynt/Zipformer-30M-RNNT-Streaming-6000h"
    zipformer_model_dir: Path = Path("data/models/asr/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
    asr_encoder_path: str = "encoder.int8.onnx"
    asr_decoder_path: str = "decoder.onnx"
    asr_joiner_path: str = "joiner.int8.onnx"
    asr_tokens_path: str = "tokens.txt"
    asr_required: bool = False

    # Runtime
    sherpa_provider: str = "cpu"
    asr_num_threads: int = Field(default=2, ge=1, le=32)
    asr_sample_rate: int = Field(default=16000, ge=8000, le=48000)
    asr_feature_dim: int = Field(default=80, ge=1, le=256)
    asr_chunk_size: int = Field(default=320, ge=64, le=4096)
    asr_max_concurrent_sessions: int = Field(default=10, ge=1, le=100)

    # Endpoint detection (tuned for Vietnamese)
    endpoint_rule1_silence: float = Field(default=2.4, ge=0.5, le=5.0)
    endpoint_rule2_silence: float = Field(default=1.2, ge=0.3, le=3.0)
    endpoint_rule3_length: float = Field(default=20.0, ge=5.0, le=60.0)

    # WebSocket
    ws_handshake_timeout: float = Field(default=5.0, gt=0)
    ws_receive_timeout: float = Field(default=30.0, gt=0)

    def model_path(self, filename: str) -> Path:
        path = Path(filename)
        return path if path.is_absolute() else self.zipformer_model_dir / path


@lru_cache
def get_asr_server_settings() -> ASRServerSettings:
    return ASRServerSettings()
