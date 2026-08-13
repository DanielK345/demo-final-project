from enum import StrEnum

from pydantic import BaseModel, Field

from src.agents.schemas import WorkflowType
from src.agents.state import ConversationRole, DeliveryStatus


class CandidateField(StrEnum):
    PICKUP = "PICKUP"
    DESTINATION = "DESTINATION"


class ContextMessage(BaseModel):
    message_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    role: ConversationRole
    content: str = Field(min_length=1)
    delivery_status: DeliveryStatus


class BusinessContextField(BaseModel):
    path: str = Field(min_length=1)
    value: str = Field(min_length=1)


class ContextCandidate(BaseModel):
    field: CandidateField
    index: int = Field(ge=1)
    display_name: str = Field(min_length=1)
    address: str | None = None


class ContextSummary(BaseModel):
    content: str = Field(min_length=1)
    summarized_through_turn_id: str = Field(min_length=1)
    source_message_ids: list[str] = Field(default_factory=list)


class ConversationContext(BaseModel):
    """Sanitized, bounded projection for language-model consumers."""

    session_id: str = Field(min_length=1)
    raw_transcript: str
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    known_fields: list[str] = Field(default_factory=list)
    business_snapshot: list[BusinessContextField] = Field(default_factory=list)
    available_candidates: list[ContextCandidate] = Field(default_factory=list)
    recent_messages: list[ContextMessage] = Field(default_factory=list)
    conversation_summary: ContextSummary | None = None
    character_budget: int = Field(ge=1)

    @property
    def last_assistant_message(self) -> ContextMessage | None:
        return next(
            (
                message
                for message in reversed(self.recent_messages)
                if message.role is ConversationRole.ASSISTANT
                and message.delivery_status in {DeliveryStatus.DELIVERED, DeliveryStatus.INTERRUPTED}
            ),
            None,
        )

    @property
    def context_character_count(self) -> int:
        count = sum(len(field.path) + len(field.value) for field in self.business_snapshot)
        count += sum(len(field) for field in self.known_fields)
        count += sum(
            len(candidate.field.value) + len(candidate.display_name) + len(candidate.address or "")
            for candidate in self.available_candidates
        )
        count += sum(len(message.content) for message in self.recent_messages)
        if self.conversation_summary is not None:
            count += len(self.conversation_summary.content)
        return count
