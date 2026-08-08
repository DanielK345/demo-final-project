from pydantic import BaseModel

from src.schemas.common import LocationDTO


class BookingRequestDTO(BaseModel):
    session_id: str
    pickup: LocationDTO
    destination: LocationDTO
    vehicle_type: str


class BookingResponseDTO(BaseModel):
    booking_id: str
    status: str
    eta_minutes: int | None = None
