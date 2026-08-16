from pydantic import BaseModel, Field


class VoiceTurnResponseDTO(BaseModel):
    transcript: str
    stt_confidence: float = Field(ge=0, le=1)
    message_id: str
    action: str
    message: str
    state: dict[str, object] = Field(default_factory=dict)
    booking: dict[str, object] | None = None
    audio_base64: str | None = None
    audio_mime_type: str = "audio/mpeg"
    voice_provider: str
    transcript_rewrite: dict[str, object] = Field(default_factory=dict)
