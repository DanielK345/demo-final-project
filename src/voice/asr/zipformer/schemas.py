from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    language: str = "vi"
    audio_duration_ms: int = Field(ge=0)
    queue_wait_ms: int = Field(ge=0)
    preprocessing_ms: int = Field(ge=0)
    inference_ms: int = Field(ge=0)
    processing_ms: int = Field(ge=0)
    realtime_factor: float = Field(ge=0)
    request_id: str
    model: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
