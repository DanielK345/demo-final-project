from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from src.agents.contracts.schemas import WorkflowType
from src.agents.legacy.understanding.models import CorrectionField


class DialogueAct(StrEnum):
    CONTINUE = "CONTINUE"
    REPEAT = "REPEAT"
    CORRECT = "CORRECT"
    CANCEL = "CANCEL"
    START_OVER = "START_OVER"
    HELP = "HELP"
    CHANGE_INTENT = "CHANGE_INTENT"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    GOODBYE = "GOODBYE"


class DialogueActResult(BaseModel):
    act: DialogueAct = DialogueAct.CONTINUE
    target_workflow: WorkflowType | None = None
    correction_field: CorrectionField | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    matched_evidence: list[str] = Field(default_factory=list)

    @field_validator("matched_evidence")
    @classmethod
    def normalize_evidence(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("dialogue-act evidence cannot be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("dialogue-act evidence must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_semantics(self) -> "DialogueActResult":
        if self.act is DialogueAct.CONTINUE and self.matched_evidence:
            raise ValueError("CONTINUE cannot contain matched command evidence")
        if self.act is not DialogueAct.CONTINUE and not self.matched_evidence:
            raise ValueError("recognized dialogue act requires matched evidence")
        if self.target_workflow is not None and self.act not in {
            DialogueAct.CHANGE_INTENT,
            DialogueAct.RESUME,
        }:
            raise ValueError("target workflow is only valid for change or resume")
        if self.correction_field is not None and self.act is not DialogueAct.CORRECT:
            raise ValueError("correction field is only valid for CORRECT")
        return self
