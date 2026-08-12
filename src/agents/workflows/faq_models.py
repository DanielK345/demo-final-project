from enum import StrEnum

from pydantic import BaseModel, Field


class FAQStep(StrEnum):
    WAITING_FOR_KNOWLEDGE = "WAITING_FOR_KNOWLEDGE"
    COMPLETE = "COMPLETE"


class FAQData(BaseModel):
    question: str | None = None
    sources: list[str] = Field(default_factory=list)
    answer: str | None = None
