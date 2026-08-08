from typing import Any

from pydantic import BaseModel, Field

from src.agents.schemas import WorkflowType


class AgentState(BaseModel):
    """Conversation state supplied by and returned to the backend."""

    session_id: str = Field(min_length=1)
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    collected_data: dict[str, Any] = Field(default_factory=dict)
    pending_tool_call_id: str | None = None
    retry_count: int = Field(default=0, ge=0)

    def apply(self, updates: dict[str, Any]) -> "AgentState":
        values = self.model_dump()
        values.update(updates)
        return type(self).model_validate(values)
