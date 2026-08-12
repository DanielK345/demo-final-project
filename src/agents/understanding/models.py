from enum import StrEnum

from pydantic import BaseModel, Field

from src.agents.schemas import WorkflowType


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


class CorrectionField(StrEnum):
    PICKUP = "PICKUP"
    DESTINATION = "DESTINATION"
    PHONE_NUMBER = "PHONE_NUMBER"
    VEHICLE_TYPE = "VEHICLE_TYPE"


class Correction(BaseModel):
    field: CorrectionField
    value: str = Field(min_length=1)


class UnderstandingContext(BaseModel):
    session_id: str = Field(min_length=1)
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    known_fields: list[str] = Field(default_factory=list)


class UnderstandingResult(BaseModel):
    intent: UnderstandingIntent = UnderstandingIntent.UNKNOWN
    pickup_query: str | None = None
    destination_query: str | None = None
    vehicle_type: str | None = None
    phone_number: str | None = None
    booking_id: str | None = None
    confirmation: ConfirmationIntent = ConfirmationIntent.NOT_APPLICABLE
    corrections: list[Correction] = Field(default_factory=list)
    handoff_reason: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
