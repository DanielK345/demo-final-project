from enum import StrEnum

from pydantic import BaseModel, Field

from src.agents.tools.schemas import PlaceCandidate


class BookingStep(StrEnum):
    COLLECT_PICKUP = "COLLECT_PICKUP"
    WAITING_FOR_PICKUP_RESULT = "WAITING_FOR_PICKUP_RESULT"
    SELECT_PICKUP_CANDIDATE = "SELECT_PICKUP_CANDIDATE"
    COLLECT_DESTINATION = "COLLECT_DESTINATION"
    WAITING_FOR_DESTINATION_RESULT = "WAITING_FOR_DESTINATION_RESULT"
    SELECT_DESTINATION_CANDIDATE = "SELECT_DESTINATION_CANDIDATE"
    COLLECT_VEHICLE_TYPE = "COLLECT_VEHICLE_TYPE"
    COLLECT_PHONE = "COLLECT_PHONE"
    CONFIRM = "CONFIRM"
    WAITING_FOR_BOOKING_RESULT = "WAITING_FOR_BOOKING_RESULT"
    COMPLETE = "COMPLETE"


class VehicleType(StrEnum):
    FOUR_SEAT = "4_SEAT"
    SEVEN_SEAT = "7_SEAT"
    PREMIUM = "PREMIUM"


class BookingData(BaseModel):
    pickup_query: str | None = None
    pickup: PlaceCandidate | None = None
    pickup_candidates: list[PlaceCandidate] = Field(default_factory=list)
    destination_query: str | None = None
    destination: PlaceCandidate | None = None
    destination_candidates: list[PlaceCandidate] = Field(default_factory=list)
    vehicle_type: VehicleType | None = None
    phone_number: str | None = None
    booking_id: str | None = None
    booking_status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)
    fare_amount: float | None = Field(default=None, ge=0)
    currency: str | None = None
