from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.voice.asr.zipformer.config import ZipformerSettings
from src.voice.asr.zipformer.errors import ASRErrorCode, ZipformerASRError

_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".webm"}
_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
    "video/webm",
}


@dataclass(frozen=True)
class DecodedAudio:
    samples: np.ndarray
    duration_ms: int
    preprocessing_ms: int


def validate_upload(data: bytes, *, filename: str, mime_type: str, settings: ZipformerSettings) -> None:
    if not data:
        raise ZipformerASRError(ASRErrorCode.EMPTY_AUDIO, "Audio file is empty", status_code=400)
    if len(data) > settings.max_audio_size_mb * 1024 * 1024:
        raise ZipformerASRError(ASRErrorCode.AUDIO_TOO_LARGE, "Audio file exceeds size limit", status_code=413)
    extension = Path(filename).suffix.lower()
    normalized_mime = mime_type.partition(";")[0].strip().lower()
    if extension not in _ALLOWED_EXTENSIONS or normalized_mime not in _ALLOWED_MIME_TYPES:
        raise ZipformerASRError(
            ASRErrorCode.UNSUPPORTED_AUDIO,
            "Supported formats are WAV, MP3, M4A, OGG, and WebM",
            status_code=415,
        )


def decode_audio(data: bytes, *, settings: ZipformerSettings) -> DecodedAudio:
    started = time.perf_counter()
    executable = shutil.which(settings.asr_ffmpeg_path)
    if not executable:
        raise ZipformerASRError(
            ASRErrorCode.MODEL_UNAVAILABLE,
            "FFmpeg is unavailable on the ASR server",
            status_code=503,
        )
    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-t",
        str(settings.max_audio_duration_seconds + 0.25),
        "-ac",
        "1",
        "-ar",
        str(settings.asr_sample_rate),
        "-f",
        "f32le",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            input=data,
            capture_output=True,
            check=False,
            timeout=settings.max_audio_duration_seconds + 15,
        )
    except subprocess.TimeoutExpired as exc:
        raise ZipformerASRError(ASRErrorCode.INVALID_AUDIO, "Audio decoding timed out", status_code=422) from exc
    if completed.returncode != 0 or not completed.stdout:
        raise ZipformerASRError(ASRErrorCode.INVALID_AUDIO, "Audio cannot be decoded", status_code=422)
    samples = np.frombuffer(completed.stdout, dtype="<f4").copy()
    if not samples.size or not np.isfinite(samples).all():
        raise ZipformerASRError(ASRErrorCode.INVALID_AUDIO, "Decoded audio is invalid", status_code=422)
    duration_seconds = samples.size / settings.asr_sample_rate
    if duration_seconds > settings.max_audio_duration_seconds:
        raise ZipformerASRError(ASRErrorCode.AUDIO_TOO_LONG, "Audio exceeds duration limit", status_code=413)
    return DecodedAudio(
        samples=np.clip(samples, -1.0, 1.0),
        duration_ms=round(duration_seconds * 1000),
        preprocessing_ms=round((time.perf_counter() - started) * 1000),
    )


def pcm16_to_float32(data: bytes) -> np.ndarray:
    if not data or len(data) % 2:
        raise ZipformerASRError(ASRErrorCode.INVALID_AUDIO, "PCM16 audio is empty or truncated", status_code=422)
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
