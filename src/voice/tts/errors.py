from __future__ import annotations

from enum import StrEnum


class TTSErrorCode(StrEnum):
    OUTPUT_BLOCKED = "TTS_OUTPUT_BLOCKED"
    PROVIDER_FAILED = "TTS_PROVIDER_FAILED"
    TIMEOUT = "TTS_TIMEOUT"
    INVALID_AUDIO = "TTS_INVALID_AUDIO"
    QUEUE_FULL = "TTS_QUEUE_FULL"
    UNAVAILABLE = "TTS_UNAVAILABLE"


class TTSError(RuntimeError):
    def __init__(self, code: TTSErrorCode, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code

