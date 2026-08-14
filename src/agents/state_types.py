from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from src.agents.schemas import WorkflowType

_RESUMABLE_STEPS = {
    WorkflowType.RIDE_BOOKING: {
        "COLLECT_PICKUP",
        "SELECT_PICKUP_CANDIDATE",
        "COLLECT_DESTINATION",
        "SELECT_DESTINATION_CANDIDATE",
        "COLLECT_VEHICLE",
        "SELECT_VEHICLE_OPTION",
        "COLLECT_PHONE",
        "SELECT_CORRECTION_FIELD",
        "CONFIRM",
        "CONFIRM_CANCEL",
    },
    WorkflowType.TRIP_LOOKUP: {"COLLECT_IDENTIFIER", "SELECT_TRIP"},
}


class ConfirmationStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class InterruptionReason(StrEnum):
    USER_PAUSE = "USER_PAUSE"
    FAQ = "FAQ"
    CHANGE_INTENT = "CHANGE_INTENT"


class InterruptedWorkflow(BaseModel):
    workflow: WorkflowType
    step: str = Field(min_length=1)
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED
    retry_count: int = Field(default=0, ge=0)
    reason: InterruptionReason

    @field_validator("step")
    @classmethod
    def normalize_step(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("interrupted workflow step cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_workflow(self) -> "InterruptedWorkflow":
        if self.workflow not in {
            WorkflowType.RIDE_BOOKING,
            WorkflowType.TRIP_LOOKUP,
        }:
            raise ValueError("only booking and trip lookup can be interrupted")
        if self.step not in _RESUMABLE_STEPS[self.workflow]:
            raise ValueError("interrupted workflow step is not resumable")
        return self
