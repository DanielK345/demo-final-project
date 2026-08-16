from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np

from src.voice.tts.errors import TTSError, TTSErrorCode


@dataclass(frozen=True)
class ValidatedAudio:
    codec: str
    sample_rate: int
    channels: int
    duration_ms: int
    rms: float
    peak: float
    silence_ratio: float
    clipped_ratio: float


class TTSAudioValidator:
    def __init__(
        self,
        *,
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
        max_audio_bytes: int = 5_242_880,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self.max_audio_bytes = max_audio_bytes
        self.timeout_seconds = timeout_seconds

    def validate(self, audio: bytes, *, expected_mime: str = "audio/mpeg") -> ValidatedAudio:
        if len(audio) < 512:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS returned empty or incomplete audio")
        if len(audio) > self.max_audio_bytes:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio exceeds configured size limit")
        ffprobe = shutil.which(self.ffprobe_path)
        ffmpeg = shutil.which(self.ffmpeg_path)
        if not ffprobe or not ffmpeg:
            raise TTSError(TTSErrorCode.UNAVAILABLE, "FFmpeg audio validation tools are unavailable")

        probe = self._run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,sample_rate,channels:format=duration",
                "-of",
                "json",
                "pipe:0",
            ],
            audio,
        )
        try:
            payload = json.loads(probe.stdout)
            stream = payload["streams"][0]
            codec = str(stream["codec_name"])
            sample_rate = int(stream["sample_rate"])
            channels = int(stream["channels"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio metadata is invalid") from exc
        if expected_mime == "audio/mpeg" and codec not in {"mp3", "mp2"}:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio codec does not match its MIME type")
        if sample_rate < 8_000 or sample_rate > 48_000 or channels not in {1, 2}:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio format is outside supported limits")
        decoded = self._run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-f",
                "f32le",
                "pipe:1",
            ],
            audio,
        )
        samples = np.frombuffer(decoded.stdout, dtype="<f4")
        if not samples.size or not np.isfinite(samples).all():
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio cannot be decoded to finite PCM")
        duration_ms = round(samples.size / 24_000 * 1000)
        if duration_ms < 200 or duration_ms > 120_000:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio duration is invalid")
        absolute = np.abs(samples)
        rms = math.sqrt(float(np.mean(np.square(samples, dtype=np.float64))))
        peak = float(np.max(absolute))
        silence_ratio = float(np.mean(absolute < 0.002))
        clipped_ratio = float(np.mean(absolute >= 0.999))
        if rms < 0.003 or peak < 0.02 or silence_ratio > 0.98:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio is silent or too quiet")
        if clipped_ratio > 0.01:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio contains excessive clipping")
        return ValidatedAudio(
            codec=codec,
            sample_rate=sample_rate,
            channels=channels,
            duration_ms=duration_ms,
            rms=round(rms, 6),
            peak=round(peak, 6),
            silence_ratio=round(silence_ratio, 6),
            clipped_ratio=round(clipped_ratio, 6),
        )

    def _run(self, command: list[str], audio: bytes) -> subprocess.CompletedProcess[bytes]:
        try:
            completed = subprocess.run(
                command,
                input=audio,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio validation timed out") from exc
        if completed.returncode != 0 or not completed.stdout:
            raise TTSError(TTSErrorCode.INVALID_AUDIO, "TTS audio is corrupt or truncated")
        return completed

