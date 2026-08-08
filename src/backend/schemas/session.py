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
