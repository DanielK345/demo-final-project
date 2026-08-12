from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from src.agents.schemas import ToolName, WorkflowType


class ConfirmationStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class ConversationRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class ConversationMessage(BaseModel):
    role: ConversationRole
    content: str = Field(min_length=1, max_length=2000)


class AgentState(BaseModel):
    """Conversation state supplied by and returned to the backend."""

    max_history_messages: ClassVar[int] = 20

    session_id: str = Field(min_length=1)
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    collected_data: dict[str, Any] = Field(default_factory=dict)
    pending_tool_call_id: str | None = None
    pending_tool_name: ToolName | None = None
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED
    retry_count: int = Field(default=0, ge=0)
    last_stt_confidence: float | None = Field(default=None, ge=0, le=1)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    state_version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_state_invariants(self) -> "AgentState":
        if self.current_step is not None and self.current_workflow is None:
            raise ValueError("current_step requires an active workflow")

        has_pending_id = self.pending_tool_call_id is not None
        has_pending_name = self.pending_tool_name is not None
        if has_pending_id != has_pending_name:
            raise ValueError(
                "pending_tool_call_id and pending_tool_name must be set together"
            )

        if len(self.conversation_history) > self.max_history_messages:
            raise ValueError(
                f"conversation_history cannot exceed {self.max_history_messages} messages"
            )
        return self

    def apply(self, updates: dict[str, Any]) -> "AgentState":
        protected_fields = {"session_id", "state_version"}.intersection(updates)
        if protected_fields:
            fields = ", ".join(sorted(protected_fields))
            raise ValueError(f"state updates cannot modify protected fields: {fields}")

        values = self.model_dump()
        values.update(updates)
        values["state_version"] = self.state_version + 1
        return type(self).model_validate(values)

    def append_message(self, message: ConversationMessage) -> "AgentState":
        history = [*self.conversation_history, message]
        bounded_history = history[-self.max_history_messages :]
        return self.apply({"conversation_history": bounded_history})
