from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from src.agents.tools.schemas import PlaceCandidate, VehicleOption
from src.agents.understanding.models import CorrectionField


class BookingStep(StrEnum):
    COLLECT_PICKUP = "COLLECT_PICKUP"
    WAITING_FOR_PICKUP_RESULT = "WAITING_FOR_PICKUP_RESULT"
    SELECT_PICKUP_CANDIDATE = "SELECT_PICKUP_CANDIDATE"
    COLLECT_DESTINATION = "COLLECT_DESTINATION"
    WAITING_FOR_DESTINATION_RESULT = "WAITING_FOR_DESTINATION_RESULT"
    SELECT_DESTINATION_CANDIDATE = "SELECT_DESTINATION_CANDIDATE"
    COLLECT_VEHICLE = "COLLECT_VEHICLE"
    WAITING_FOR_VEHICLE_OPTIONS = "WAITING_FOR_VEHICLE_OPTIONS"
    SELECT_VEHICLE_OPTION = "SELECT_VEHICLE_OPTION"
    WAITING_FOR_FARE_ESTIMATE = "WAITING_FOR_FARE_ESTIMATE"
    COLLECT_PHONE = "COLLECT_PHONE"
    SELECT_CORRECTION_FIELD = "SELECT_CORRECTION_FIELD"
    CONFIRM = "CONFIRM"
    WAITING_FOR_BOOKING_RESULT = "WAITING_FOR_BOOKING_RESULT"
    CONFIRM_CANCEL = "CONFIRM_CANCEL"
    WAITING_FOR_CANCELLATION_RESULT = "WAITING_FOR_CANCELLATION_RESULT"
    COMPLETE = "COMPLETE"


class BookingData(BaseModel):
    pickup_query: str | None = None
    pickup: PlaceCandidate | None = None
    pickup_candidates: list[PlaceCandidate] = Field(default_factory=list)
    destination_query: str | None = None
    destination: PlaceCandidate | None = None
    destination_candidates: list[PlaceCandidate] = Field(default_factory=list)
    vehicle_type: str | None = None
    selected_vehicle_option_id: str | None = None
    vehicle_display_name: str | None = None
    passenger_count: int | None = Field(default=None, ge=1, le=50)
    luggage_count: int | None = Field(default=None, ge=0, le=50)
    vehicle_preference: str | None = None
    vehicle_options: list[VehicleOption] = Field(default_factory=list)
    recommended_vehicle_option_id: str | None = None
    fare_estimate_id: str | None = None
    estimated_fare_amount: float | None = Field(default=None, ge=0)
    estimated_currency: str | None = None
    estimated_eta_minutes: int | None = Field(default=None, ge=0)
    estimated_distance_km: float | None = Field(default=None, ge=0)
    phone_number: str | None = None
    correction_field: CorrectionField | None = None
    correction_return_step: BookingStep | None = None
    booking_id: str | None = None
    booking_status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)
    fare_amount: float | None = Field(default=None, ge=0)
    currency: str | None = None
    completed_booking_call_id: str | None = None
    completed_cancellation_call_id: str | None = None

    @model_validator(mode="after")
    def validate_correction_state(self) -> "BookingData":
        if self.correction_return_step not in {None, BookingStep.CONFIRM}:
            raise ValueError("booking corrections can only return to confirmation")
        return self
