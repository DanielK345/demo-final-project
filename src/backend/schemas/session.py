from typing import Literal

from pydantic import BaseModel, Field

from src.backend.schemas.common import LocationDTO


class SessionDTO(BaseModel):
    session_id: str
    call_id: str
    intent: str | None = None
    pickup: LocationDTO | None = None
    destination: LocationDTO | None = None
    vehicle_type: str | None = None
    confirmation_status: str = Field(default="pending")
    failed_count: int = Field(default=0, ge=0)
    booking_id: str | None = None
    handoff_triggered: bool = False
    status: str = "ACTIVE"
    channel: str = "WEB_TEXT"
    current_workflow: str | None = None
    current_step: str | None = None
    has_resumable_voice_state: bool = False
    voice_session_terminal: bool = False


class CreateSessionDTO(BaseModel):
    channel: Literal["WEB_VOICE", "WEB_TEXT"] = "WEB_TEXT"
    device_id: str | None = Field(default=None, max_length=128)


class SessionCreatedDTO(BaseModel):
    session_id: str
    status: str
    channel: str
    created_at: str


class SessionMessageDTO(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    source: Literal["TEXT", "VOICE"] = "TEXT"
    stt_confidence: float | None = Field(default=None, ge=0, le=1)


class SessionMessageResponseDTO(BaseModel):
    message_id: str
    action: str
    message: str
    state: dict[str, object]
    booking: dict[str, object] | None = None


class SessionFeedbackDTO(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class SessionFeedbackResponseDTO(BaseModel):
    session_id: str
    feedback: dict[str, object]


class EndSessionDTO(BaseModel):
    reason: str = Field(default="USER_ENDED", min_length=1, max_length=64)


class EndSessionResponseDTO(BaseModel):
    session_id: str
    status: str
    ended_at: str


class SessionResetResponseDTO(BaseModel):
    """Reset conversation state without invalidating the authenticated session."""

    session_id: str
    status: str
    reset_at: str


class SessionUpdateDTO(BaseModel):
    intent: str | None = None
    pickup: LocationDTO | None = None
    destination: LocationDTO | None = None
    vehicle_type: str | None = None
    confirmation_status: str | None = None
    failed_count: int | None = Field(default=None, ge=0)
    booking_id: str | None = None
    handoff_triggered: bool | None = None


class SessionResumeResponseDTO(BaseModel):
    session_id: str
    status: str


class SessionHistorySummaryDTO(BaseModel):
    """1 dòng trong danh sách lịch sử trò chuyện — `GET /api/v1/sessions/history`."""

    session_id: str
    channel: str
    status: str
    created_at: str | None = None
    message_count: int
    preview: str


class SessionHistoryMessageDTO(BaseModel):
    timestamp: str
    role: Literal["user", "agent"]
    text: str
    source: str | None = None
    stt_confidence: float | None = None
    action: str | None = None


class SessionTranscriptDTO(BaseModel):
    """Toàn bộ nội dung 1 cuộc trò chuyện —
    `GET /api/v1/sessions/history/{session_id}`."""

    session_id: str
    channel: str
    status: str
    created_at: str | None = None
    ended_at: str | None = None
    messages: list[SessionHistoryMessageDTO]
