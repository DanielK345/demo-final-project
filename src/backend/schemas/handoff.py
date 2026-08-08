from pydantic import BaseModel


class HandoffDTO(BaseModel):
    session_id: str
    reason: str
    summary: str
    pending_action: str | None = None


class HandoffResponseDTO(BaseModel):
    handoff_id: str
    session_id: str
    reason: str
    summary: str
    pending_action: str | None = None
    status: str


class HandoffAcceptanceDTO(BaseModel):
    handoff_id: str
    status: str
