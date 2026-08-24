from enum import StrEnum

from pydantic import BaseModel, Field

from src.agents.contracts.schemas import WorkflowType
from src.agents.core.booking_types import CorrectionField, VehicleType
from src.agents.legacy.context_models import (
    BusinessContextField,
    ContextCandidate,
    ContextMessage,
    ContextSummary,
)
from src.agents.legacy.understanding.rewrite_models import ResolvedReference


class UnderstandingIntent(StrEnum):
    RIDE_BOOKING = "RIDE_BOOKING"
    TRIP_LOOKUP = "TRIP_LOOKUP"
    FAQ = "FAQ"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    UNKNOWN = "UNKNOWN"


class ConfirmationIntent(StrEnum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BookingSelectionTarget(StrEnum):
    PICKUP = "PICKUP"
    DESTINATION = "DESTINATION"
    VEHICLE = "VEHICLE"


class BookingSelection(BaseModel):
    target: BookingSelectionTarget
    index: int = Field(ge=1, le=9)


class Correction(BaseModel):
    field: CorrectionField
    value: str | None = Field(default=None, min_length=1)


class UnderstandingContext(BaseModel):
    session_id: str = Field(min_length=1)
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    known_fields: list[str] = Field(default_factory=list)
    business_snapshot: list[BusinessContextField] = Field(default_factory=list)
    available_candidates: list[ContextCandidate] = Field(default_factory=list)
    recent_messages: list[ContextMessage] = Field(default_factory=list)
    conversation_summary: ContextSummary | None = None
    rewrite_applied: bool = False
    rewrite_evidence: list[ResolvedReference] = Field(default_factory=list)
    rewrite_ambiguities: list[str] = Field(default_factory=list)


class UnderstandingResult(BaseModel):
    intent: UnderstandingIntent = UnderstandingIntent.UNKNOWN
    pickup_query: str | None = None
    destination_query: str | None = None
    phone_number: str | None = None
    vehicle_type: VehicleType | None = None
    passenger_count: int | None = Field(default=None, ge=1, le=50)
    luggage_count: int | None = Field(default=None, ge=0, le=50)
    vehicle_preference: str | None = Field(default=None, max_length=200)
    booking_id: str | None = None
    confirmation: ConfirmationIntent = ConfirmationIntent.NOT_APPLICABLE
    correction_requested: bool = False
    corrections: list[Correction] = Field(default_factory=list)
    selection: BookingSelection | None = None
    handoff_reason: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
