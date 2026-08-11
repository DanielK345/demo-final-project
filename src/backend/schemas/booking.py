from pydantic import BaseModel

from src.backend.schemas.common import LocationDTO


class BookingRequestDTO(BaseModel):
    session_id: str
    pickup: LocationDTO
    destination: LocationDTO
    vehicle_type: str
    fare_confirmed: bool = False
    estimated_fare: int | None = None


class BookingResponseDTO(BaseModel):
    booking_id: str
    status: str
    eta_minutes: int | None = None
    estimated_fare: int | None = None
    currency: str = "VND"
