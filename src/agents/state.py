from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.agents.schemas import ToolName, WorkflowType
from src.agents.state_types import ConfirmationStatus, InterruptedWorkflow


class ConversationRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class ConversationMessageType(StrEnum):
    USER_TRANSCRIPT = "USER_TRANSCRIPT"
    ASSISTANT_SPEECH = "ASSISTANT_SPEECH"
    TOOL_SUMMARY = "TOOL_SUMMARY"
    CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY"


class DeliveryStatus(StrEnum):
    FINAL = "FINAL"
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


class ConversationMessage(BaseModel):
    message_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    role: ConversationRole
    message_type: ConversationMessageType
    content: str = Field(min_length=1, max_length=2000)
    delivery_status: DeliveryStatus
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    spoken_content: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("message_id", "turn_id")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message identity cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_message_semantics(self) -> "ConversationMessage":
        allowed_types = {
            ConversationRole.USER: {ConversationMessageType.USER_TRANSCRIPT},
            ConversationRole.ASSISTANT: {
                ConversationMessageType.ASSISTANT_SPEECH,
                ConversationMessageType.CONVERSATION_SUMMARY,
            },
            ConversationRole.TOOL: {ConversationMessageType.TOOL_SUMMARY},
        }
        if self.message_type not in allowed_types[self.role]:
            raise ValueError("message type is not valid for the selected role")

        if self.message_type is ConversationMessageType.ASSISTANT_SPEECH:
            allowed_statuses = {
                DeliveryStatus.PENDING,
                DeliveryStatus.DELIVERED,
                DeliveryStatus.INTERRUPTED,
                DeliveryStatus.FAILED,
            }
            if self.delivery_status not in allowed_statuses:
                raise ValueError("assistant speech has an invalid delivery status")
        elif self.delivery_status is not DeliveryStatus.FINAL:
            raise ValueError("non-speech history messages must be final")

        if self.delivery_status is DeliveryStatus.PENDING and self.spoken_content:
            raise ValueError("pending speech cannot contain spoken content")
        if self.delivery_status is DeliveryStatus.FAILED and self.spoken_content:
            raise ValueError("failed speech cannot contain spoken content")
        if self.role is not ConversationRole.ASSISTANT and self.spoken_content:
            raise ValueError("spoken content is only valid for assistant speech")

        expected_id = {
            ConversationMessageType.USER_TRANSCRIPT: f"{self.turn_id}:user",
            ConversationMessageType.ASSISTANT_SPEECH: f"{self.turn_id}:assistant",
            ConversationMessageType.CONVERSATION_SUMMARY: f"{self.turn_id}:summary",
        }.get(self.message_type)
        if expected_id is not None and self.message_id != expected_id:
            raise ValueError("message_id does not match the turn and message type")
        if self.message_type is ConversationMessageType.TOOL_SUMMARY:
            prefix = f"{self.turn_id}:tool-summary:"
            sequence = self.message_id.removeprefix(prefix)
            if not self.message_id.startswith(prefix) or not sequence.isdigit() or int(sequence) < 1:
                raise ValueError("tool summary message_id has an invalid sequence")
        return self


class AssistantDeliveryEvent(BaseModel):
    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    status: DeliveryStatus
    spoken_content: str | None = Field(default=None, max_length=2000)

    @field_validator("session_id", "turn_id", "message_id")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("delivery identity cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_delivery_event(self) -> "AssistantDeliveryEvent":
        if self.status not in {
            DeliveryStatus.DELIVERED,
            DeliveryStatus.INTERRUPTED,
            DeliveryStatus.FAILED,
        }:
            raise ValueError("delivery event requires a terminal speech status")
        if self.status is DeliveryStatus.FAILED and self.spoken_content:
            raise ValueError("failed delivery cannot contain spoken content")
        return self


class ConversationSummary(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    summarized_through_turn_id: str = Field(min_length=1)
    source_message_ids: list[str] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("summarized_through_turn_id")
    @classmethod
    def normalize_turn_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summarized turn_id cannot be blank")
        return normalized

    @model_validator(mode="after")
    def require_unique_sources(self) -> "ConversationSummary":
        if len(self.source_message_ids) != len(set(self.source_message_ids)):
            raise ValueError("conversation summary contains duplicate source messages")
        return self


class AgentState(BaseModel):
    """Conversation state supplied by and returned to the backend."""

    model_config = ConfigDict(extra="forbid")

    max_history_messages: ClassVar[int] = 20

    session_id: str = Field(min_length=1)
    current_workflow: WorkflowType | None = None
    current_step: str | None = None
    collected_data: dict[str, Any] = Field(default_factory=dict)
    pending_tool_call_id: str | None = None
    pending_tool_name: ToolName | None = None
    confirmation: ConfirmationStatus = ConfirmationStatus.NOT_REQUESTED
    retry_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    last_stt_confidence: float | None = Field(default=None, ge=0, le=1)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    conversation_summary: ConversationSummary | None = None
    interrupted_workflow: InterruptedWorkflow | None = None
    state_version: int = Field(default=0, ge=0)

    @field_validator("session_id")
    @classmethod
    def normalize_session_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_id cannot be blank")
        return normalized

    @field_validator("pending_tool_call_id")
    @classmethod
    def normalize_pending_tool_call_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("pending_tool_call_id cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_state_invariants(self) -> "AgentState":
        if self.current_step is not None and self.current_workflow is None:
            raise ValueError("current_step requires an active workflow")
        if self.interrupted_workflow is not None and self.current_workflow is self.interrupted_workflow.workflow:
            raise ValueError("active and interrupted workflow must be different")

        has_pending_id = self.pending_tool_call_id is not None
        has_pending_name = self.pending_tool_name is not None
        if has_pending_id != has_pending_name:
            raise ValueError("pending_tool_call_id and pending_tool_name must be set together")

        if len(self.conversation_history) > self.max_history_messages:
            raise ValueError(f"conversation_history cannot exceed {self.max_history_messages} messages")

        message_ids = [message.message_id for message in self.conversation_history]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("conversation_history contains duplicate message_id values")

        user_turn_ids = [
            message.turn_id
            for message in self.conversation_history
            if message.message_type is ConversationMessageType.USER_TRANSCRIPT
        ]
        if len(user_turn_ids) != len(set(user_turn_ids)):
            raise ValueError("a turn cannot contain multiple user transcripts")
        return self

    def apply(self, updates: dict[str, Any]) -> "AgentState":
        unknown_fields = set(updates).difference(type(self).model_fields)
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ValueError(f"state updates contain unknown fields: {fields}")
        protected_fields = {"session_id", "state_version"}.intersection(updates)
        if protected_fields:
            fields = ", ".join(sorted(protected_fields))
            raise ValueError(f"state updates cannot modify protected fields: {fields}")

        values = self.model_dump()
        values.update(updates)
        values["state_version"] = self.state_version + 1
        return type(self).model_validate(values)

    def append_message(self, message: ConversationMessage) -> "AgentState":
        if any(existing.message_id == message.message_id for existing in self.conversation_history):
            raise ValueError("conversation_history contains duplicate message_id values")
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT and any(
            existing.message_type is ConversationMessageType.USER_TRANSCRIPT and existing.turn_id == message.turn_id
            for existing in self.conversation_history
        ):
            raise ValueError("a turn cannot contain multiple user transcripts")
        history = [*self.conversation_history, message]
        bounded_history = history[-self.max_history_messages :]
        return self.apply({"conversation_history": bounded_history})
