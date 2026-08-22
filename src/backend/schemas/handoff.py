from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class HandoffStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CONNECTED = "connected"
    RESOLVED = "resolved"
    FAILED = "failed"


class HandoffDTO(BaseModel):
    session_id: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    reason_code: str = "UNABLE_TO_CONTINUE"
    summary: str = Field(min_length=1, max_length=4000)
    pending_action: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    severity: str = "NORMAL"
    queue: str = "GENERAL_OPERATOR"
    requires_immediate_transfer: bool = False


class HandoffResponseDTO(BaseModel):
    handoff_id: str
    session_id: str
    reason: str
    reason_code: str
    summary: str
    pending_action: str | None = None
    priority: int
    severity: str
    queue: str
    requires_immediate_transfer: bool
    status: HandoffStatus
    created_at: datetime
    accepted_at: datetime | None = None
    connected_at: datetime | None = None
    resolved_at: datetime | None = None
    operator_id: str | None = None
    room_name: str | None = None
    context_snapshot: dict[str, object] | None = None


class HandoffAcceptanceDTO(BaseModel):
    handoff_id: str
    status: HandoffStatus
    accepted_at: datetime
    operator_id: str | None = None
