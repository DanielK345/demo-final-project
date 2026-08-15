from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.agents.core.booking_types import CorrectionField
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    EstimateFareResult,
    GetVehicleOptionsResult,
    PlaceCandidate,
    PlaceResolutionStatus,
    SearchPlaceResult,
    VehicleOption,
)


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
    pickup_resolution: PlaceResolutionStatus = PlaceResolutionStatus.UNRESOLVED
    pickup: PlaceCandidate | None = None
    pickup_candidates: list[PlaceCandidate] = Field(default_factory=list)
    destination_query: str | None = None
    destination_resolution: PlaceResolutionStatus = PlaceResolutionStatus.UNRESOLVED
    destination: PlaceCandidate | None = None
    destination_candidates: list[PlaceCandidate] = Field(default_factory=list)
    pending_location_target: Literal["pickup", "destination"] | None = None
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
        if self.pickup is not None:
            self.pickup_resolution = PlaceResolutionStatus.RESOLVED
        elif self.pickup_candidates:
            self.pickup_resolution = PlaceResolutionStatus.AMBIGUOUS
        if self.destination is not None:
            self.destination_resolution = PlaceResolutionStatus.RESOLVED
        elif self.destination_candidates:
            self.destination_resolution = PlaceResolutionStatus.AMBIGUOUS
        return self


@dataclass(frozen=True)
class PlaceResolution:
    data: BookingData
    status: PlaceResolutionStatus


def clear_vehicle_selection(data: BookingData) -> BookingData:
    return data.model_copy(
        update={
            "vehicle_type": None,
            "selected_vehicle_option_id": None,
            "vehicle_display_name": None,
            "vehicle_options": [],
            "recommended_vehicle_option_id": None,
        },
        deep=True,
    )


def clear_fare_estimate(data: BookingData) -> BookingData:
    return data.model_copy(
        update={
            "fare_estimate_id": None,
            "estimated_fare_amount": None,
            "estimated_currency": None,
            "estimated_eta_minutes": None,
            "estimated_distance_km": None,
        },
        deep=True,
    )


def clear_completed_booking(data: BookingData) -> BookingData:
    return data.model_copy(
        update={
            "booking_id": None,
            "booking_status": None,
            "eta_minutes": None,
            "fare_amount": None,
            "currency": None,
            "completed_booking_call_id": None,
            "completed_cancellation_call_id": None,
        },
        deep=True,
    )


def draft_from_completed_booking(data: BookingData) -> BookingData:
    return clear_fare_estimate(clear_vehicle_selection(clear_completed_booking(data)))


def reduce_place_result(
    data: BookingData,
    result: SearchPlaceResult,
    *,
    pickup: bool,
) -> PlaceResolution:
    updated = data.model_copy(deep=True)
    candidates = result.candidates
    status = result.status or PlaceResolutionStatus.NOT_FOUND
    if status in {
        PlaceResolutionStatus.NOT_FOUND,
        PlaceResolutionStatus.NEEDS_CLARIFICATION,
    }:
        _set_place(updated, pickup=pickup, place=None, candidates=[])
        return PlaceResolution(updated, status)
    if status is PlaceResolutionStatus.AMBIGUOUS:
        _set_place(updated, pickup=pickup, place=None, candidates=candidates)
        return PlaceResolution(updated, status)
    _set_place(updated, pickup=pickup, place=candidates[0], candidates=[])
    return PlaceResolution(updated, PlaceResolutionStatus.RESOLVED)


def apply_vehicle_options_result(
    data: BookingData,
    result: GetVehicleOptionsResult,
) -> BookingData:
    available = [option for option in result.options if option.available]
    return data.model_copy(update={"vehicle_options": available}, deep=True)


def apply_fare_result(
    data: BookingData,
    result: EstimateFareResult,
) -> BookingData:
    return data.model_copy(
        update={
            "fare_estimate_id": result.estimate_id,
            "estimated_fare_amount": result.fare_amount,
            "estimated_currency": result.currency,
            "estimated_eta_minutes": result.eta_minutes,
            "estimated_distance_km": result.distance_km,
        },
        deep=True,
    )


def apply_booking_result(
    data: BookingData,
    result: CreateBookingResult,
    *,
    completed_call_id: str | None,
) -> BookingData:
    return data.model_copy(
        update={
            "booking_id": result.booking_id,
            "booking_status": result.status,
            "eta_minutes": result.eta_minutes,
            "fare_amount": result.fare_amount,
            "currency": result.currency,
            "completed_booking_call_id": completed_call_id,
        },
        deep=True,
    )


def apply_cancellation_result(
    data: BookingData,
    result: CancelBookingResult,
    *,
    completed_call_id: str | None,
) -> BookingData:
    return data.model_copy(
        update={
            "booking_status": result.status,
            "completed_cancellation_call_id": completed_call_id,
        },
        deep=True,
    )


def _set_place(
    data: BookingData,
    *,
    pickup: bool,
    place: PlaceCandidate | None,
    candidates: list[PlaceCandidate],
) -> None:
    if pickup:
        data.pickup = place
        data.pickup_candidates = candidates
    else:
        data.destination = place
        data.destination_candidates = candidates
