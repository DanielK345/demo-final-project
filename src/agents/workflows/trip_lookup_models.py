from enum import StrEnum

from pydantic import BaseModel, Field


class TripLookupStep(StrEnum):
    COLLECT_IDENTIFIER = "COLLECT_IDENTIFIER"
    WAITING_FOR_TRIP_RESULT = "WAITING_FOR_TRIP_RESULT"
    COMPLETE = "COMPLETE"


class TripLookupData(BaseModel):
    booking_id: str | None = None
    phone_number: str | None = None
    found_booking_id: str | None = None
    trip_status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)
