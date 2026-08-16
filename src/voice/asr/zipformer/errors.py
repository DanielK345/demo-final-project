from __future__ import annotations

from enum import StrEnum


class ASRErrorCode(StrEnum):
    EMPTY_AUDIO = "EMPTY_AUDIO"
    INVALID_AUDIO = "INVALID_AUDIO"
    UNSUPPORTED_AUDIO = "UNSUPPORTED_AUDIO"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    QUEUE_FULL = "QUEUE_FULL"
    INFERENCE_TIMEOUT = "INFERENCE_TIMEOUT"
    INFERENCE_FAILED = "INFERENCE_FAILED"


class ZipformerASRError(RuntimeError):
    def __init__(self, code: ASRErrorCode, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
