from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.agents.booking_types import VehicleType
from src.agents.phone_policy import is_valid_mobile_phone


class ToolPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


def _strip_required_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("value cannot be blank")
    return stripped


class SearchPlaceParams(BaseModel):
    query: str = Field(min_length=1)

    _normalize_query = field_validator("query")(_strip_required_text)


class CreateBookingParams(BaseModel):
    pickup_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    phone_number: str = Field(min_length=1)
    vehicle_type: str = Field(min_length=1)
    vehicle_option_id: str | None = Field(default=None, min_length=1)
    fare_estimate_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    passenger_count: int | None = Field(default=None, ge=1, le=50)

    _normalize_text = field_validator(
        "pickup_place_id",
        "destination_place_id",
        "phone_number",
        "vehicle_type",
        "fare_estimate_id",
        "idempotency_key",
    )(_strip_required_text)

    @field_validator("phone_number")
    @classmethod
    def require_mobile_phone(cls, value: str) -> str:
        if not is_valid_mobile_phone(value):
            raise ValueError("phone_number must be a valid Vietnamese mobile number")
        return value


class EstimateFareParams(BaseModel):
    pickup_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    vehicle_type: VehicleType

    _normalize_text = field_validator(
        "pickup_place_id",
        "destination_place_id",
    )(_strip_required_text)


class GetVehicleOptionsParams(BaseModel):
    pickup_place_id: str = Field(min_length=1)
    destination_place_id: str = Field(min_length=1)
    passenger_count: int = Field(ge=1, le=50)
    luggage_count: int | None = Field(default=None, ge=0, le=50)
    preference: str | None = Field(default=None, max_length=200)

    _normalize_text = field_validator(
        "pickup_place_id",
        "destination_place_id",
    )(_strip_required_text)


class CancelBookingParams(BaseModel):
    booking_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)

    _normalize_text = field_validator(
        "booking_id",
        "idempotency_key",
    )(_strip_required_text)


class LookupTripParams(BaseModel):
    booking_id: str | None = None
    phone_number: str | None = None

    @field_validator("booking_id", "phone_number")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_required_text(value) if value is not None else None

    @model_validator(mode="after")
    def require_identifier(self) -> "LookupTripParams":
        if not self.booking_id and not self.phone_number:
            raise ValueError("booking_id or phone_number is required")
        return self


class RetrieveKnowledgeParams(BaseModel):
    query: str = Field(min_length=1)

    _normalize_query = field_validator("query")(_strip_required_text)


class CreateHandoffParams(BaseModel):
    session_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)

    _normalize_text = field_validator("session_id", "reason")(_strip_required_text)


class PlaceCandidate(ToolPayload):
    place_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    address: str | None = None


class SearchPlaceResult(ToolPayload):
    candidates: list[PlaceCandidate] = Field(default_factory=list)


class CreateBookingResult(ToolPayload):
    booking_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    eta_minutes: int | None = Field(default=None, ge=0)
    fare_amount: float | None = Field(default=None, ge=0)
    currency: str | None = None


class EstimateFareResult(ToolPayload):
    estimate_id: str = Field(min_length=1)
    fare_amount: float = Field(ge=0)
    currency: str = Field(min_length=1)
    eta_minutes: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)


class VehicleOption(ToolPayload):
    option_id: str = Field(min_length=1)
    vehicle_type: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    capacity: int = Field(ge=1)
    luggage_capacity: int | None = Field(default=None, ge=0)
    available: bool = True
    estimate_id: str = Field(min_length=1)
    fare_amount: float = Field(ge=0)
    currency: str = Field(min_length=1)
    eta_minutes: int | None = Field(default=None, ge=0)


class GetVehicleOptionsResult(ToolPayload):
    options: list[VehicleOption] = Field(default_factory=list)


class CancelBookingResult(ToolPayload):
    booking_id: str = Field(min_length=1)
    status: str = Field(min_length=1)


class TripMatch(ToolPayload):
    booking_id: str = Field(min_length=1)
    status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)
    pickup_label: str | None = None
    destination_label: str | None = None


class LookupTripResult(ToolPayload):
    found: bool
    booking_id: str | None = None
    status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)
    trips: list[TripMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_found_trip_data(self) -> "LookupTripResult":
        has_single = bool(self.booking_id and self.status)
        if self.found and not has_single and not self.trips:
            raise ValueError("a found trip requires one trip or a list of trips")
        if not self.found and (has_single or self.trips):
            raise ValueError("a not-found result cannot contain trips")
        return self


class KnowledgeDocument(ToolPayload):
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    citation_id: str | None = None
    version: str | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("effective_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("knowledge timestamps must include a timezone")
        return value


class RetrieveKnowledgeResult(ToolPayload):
    documents: list[KnowledgeDocument] = Field(default_factory=list)


class CreateHandoffResult(ToolPayload):
    handoff_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
