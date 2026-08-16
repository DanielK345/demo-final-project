from pydantic import BaseModel, Field


class VoiceTurnResponseDTO(BaseModel):
    transcript: str

    transcript_rewritten: bool = False
    transcript_rewrite_confidence: float | None = Field(default=None, ge=0, le=1)
    transcript_rewrite_reason: str | None = None
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    message_id: str
    action: str
    message: str
    state: dict[str, object] = Field(default_factory=dict)
    booking: dict[str, object] | None = None
    audio_base64: str | None = None
    audio_mime_type: str = "audio/mpeg"
    voice_provider: str
