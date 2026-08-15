from typing import ClassVar

from pydantic import BaseModel, Field

from src.agents.contracts.schemas import ToolName


class AgentPolicy(BaseModel):
    _RETRY_LIMITS: ClassVar[dict[ToolName, int]] = {
        ToolName.SEARCH_PLACE: 3,
        ToolName.GET_VEHICLE_OPTIONS: 3,
        ToolName.ESTIMATE_FARE: 3,
        ToolName.LOOKUP_TRIP: 3,
        ToolName.RETRIEVE_KNOWLEDGE: 2,
    }
    _DEADLINES_SECONDS: ClassVar[dict[ToolName, float]] = {
        ToolName.SEARCH_PLACE: 5.0,
        ToolName.GET_VEHICLE_OPTIONS: 5.0,
        ToolName.ESTIMATE_FARE: 5.0,
        ToolName.CREATE_BOOKING: 10.0,
        ToolName.CANCEL_BOOKING: 10.0,
        ToolName.LOOKUP_TRIP: 5.0,
        ToolName.RETRIEVE_KNOWLEDGE: 8.0,
        ToolName.CREATE_HANDOFF: 10.0,
    }

    low_confidence_threshold: float = Field(default=0.5, ge=0, le=1)
    max_retry_count: int = Field(default=3, ge=1)
    max_model_failure_count: int = Field(default=3, ge=2)
    max_spoken_message_characters: int = Field(default=600, ge=1)
    max_tool_calls_per_session: int = Field(default=30, ge=1)
    min_knowledge_score: float = Field(default=0.7, ge=0, le=1)
    max_knowledge_documents: int = Field(default=5, ge=1, le=20)

    def retry_limit(self, tool_name: ToolName) -> int:
        return self._RETRY_LIMITS.get(tool_name, self.max_retry_count)

    def tool_deadline_seconds(self, tool_name: ToolName) -> float:
        return self._DEADLINES_SECONDS[tool_name]
