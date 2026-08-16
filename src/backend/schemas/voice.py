from pydantic import BaseModel, Field


class VoiceTurnResponseDTO(BaseModel):
    transcript: str

    transcript_rewritten: bool = False
    transcript_rewrite_confidence: float | None = Field(default=None, ge=0, le=1)
    transcript_rewrite_reason: str | None = None
    # Backward-compatible UI trace for the call-content dropdown.  The typed
    # fields above remain the API contract; this compact object explains whether
    # a rewrite provider was invoked without exposing raw provider errors.
    transcript_rewrite: dict[str, object] | None = None
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    message_id: str
    action: str
    message: str
    state: dict[str, object] = Field(default_factory=dict)
    booking: dict[str, object] | None = None
    audio_base64: str | None = None
    audio_mime_type: str = "audio/mpeg"
    voice_provider: str
    tts_provider: str | None = None
    tts_voice: str | None = None
    tts_fallback_used: bool = False
    tts_duration_ms: int | None = Field(default=None, ge=0)
    tts_review_decision: str | None = None
    tts_review_reason_codes: list[str] = Field(default_factory=list)
