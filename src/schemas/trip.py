from pydantic import BaseModel


class TripStatusDTO(BaseModel):
    trip_id: str
    status: str
    eta_minutes: int | None = None
