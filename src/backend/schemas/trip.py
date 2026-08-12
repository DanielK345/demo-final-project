from pydantic import BaseModel


class TripStatusDTO(BaseModel):
    trip_id: str
    status: str
    eta_minutes: int | None = None
    driver_name: str | None = None
    vehicle: str | None = None
    license_plate: str | None = None
    driver_rating: float | None = None
    driver_phone: str | None = None
