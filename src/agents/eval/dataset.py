import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.agents.eval.models import ConversationEvaluationCase


class EvaluationDataset(BaseModel):
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    scenarios: list[ConversationEvaluationCase] = Field(min_length=1)


def load_evaluation_dataset(path: str | Path) -> EvaluationDataset:
    source = Path(path)
    return EvaluationDataset.model_validate(json.loads(source.read_text(encoding="utf-8")))
