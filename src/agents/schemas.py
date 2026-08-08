from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ActionType(StrEnum):
    ASK_USER = "ASK_USER"
    RESPOND = "RESPOND"
    CALL_TOOL = "CALL_TOOL"
    HANDOFF = "HANDOFF"
    END_SESSION = "END_SESSION"


class WorkflowType(StrEnum):
    RIDE_BOOKING = "RIDE_BOOKING"
    TRIP_LOOKUP = "TRIP_LOOKUP"
    FAQ = "FAQ"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class ToolName(StrEnum):
    SEARCH_PLACE = "search_place"
    CREATE_BOOKING = "create_booking"
    LOOKUP_TRIP = "lookup_trip"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    CREATE_HANDOFF = "create_handoff"


class ToolStatus(StrEnum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class ToolResult(BaseModel):
    tool_name: ToolName
    call_id: str = Field(min_length=1)
    status: ToolStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ToolResult":
        if self.status is ToolStatus.ERROR and not self.error:
            raise ValueError("error details are required for a failed tool result")
        if self.status is ToolStatus.SUCCESS and self.error is not None:
            raise ValueError("a successful tool result cannot contain an error")
        return self


class AgentInput(BaseModel):
    session_id: str = Field(min_length=1)
    transcript: str = ""
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    tool_result: ToolResult | None = None

    @model_validator(mode="after")
    def require_transcript_or_tool_result(self) -> "AgentInput":
        if not self.transcript.strip() and self.tool_result is None:
            raise ValueError("transcript or tool_result is required")
        return self


class ToolCall(BaseModel):
    tool_name: ToolName
    call_id: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class AgentAction(BaseModel):
    action_type: ActionType
    message: str | None = None
    tool_call: ToolCall | None = None
    state_updates: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "AgentAction":
        if self.action_type is ActionType.CALL_TOOL and self.tool_call is None:
            raise ValueError("CALL_TOOL requires tool_call")
        if self.action_type is not ActionType.CALL_TOOL and self.tool_call is not None:
            raise ValueError("tool_call is only valid for CALL_TOOL")
        return self
