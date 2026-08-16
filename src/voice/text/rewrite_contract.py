"""Provider-independent contract for post-ASR transcript normalization."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class TranscriptRewriteResult(BaseModel):
    raw_text: str
    normalized_text: str
    applied: bool = False
    requires_clarification: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str
    model: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class TranscriptRewriter(Protocol):
    async def rewrite(
        self,
        text: str,
        *,
        session_context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> TranscriptRewriteResult: ...
