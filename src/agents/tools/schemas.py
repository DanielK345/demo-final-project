from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    _normalize_text = field_validator(
        "pickup_place_id",
        "destination_place_id",
        "phone_number",
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

    _normalize_text = field_validator("session_id", "reason")(
        _strip_required_text
    )


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


class LookupTripResult(ToolPayload):
    found: bool
    booking_id: str | None = None
    status: str | None = None
    eta_minutes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_found_trip_data(self) -> "LookupTripResult":
        if self.found and (not self.booking_id or not self.status):
            raise ValueError("a found trip requires booking_id and status")
        return self


class KnowledgeDocument(ToolPayload):
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveKnowledgeResult(ToolPayload):
    documents: list[KnowledgeDocument] = Field(default_factory=list)


class CreateHandoffResult(ToolPayload):
    handoff_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
