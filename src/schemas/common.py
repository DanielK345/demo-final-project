from pydantic import BaseModel, Field


class LocationDTO(BaseModel):
    name: str = Field(..., min_length=1)
    lat: float
    lng: float
    place_id: str | None = None
