from pydantic import BaseModel, Field, model_validator

from src.agents.schemas import ActionType, AgentInput, ToolName, WorkflowType
from src.agents.state import AgentState


class EvaluationCase(BaseModel):
    name: str = Field(min_length=1)
    agent_input: AgentInput
    state: AgentState | None = None
    expected_action_type: ActionType
    expected_workflow: WorkflowType | None = None
    expected_tool_name: ToolName | None = None

    @model_validator(mode="after")
    def validate_expected_tool(self) -> "EvaluationCase":
        if (
            self.expected_action_type is ActionType.CALL_TOOL
            and self.expected_tool_name is None
        ):
            raise ValueError("CALL_TOOL evaluation requires expected_tool_name")
        return self


class EvaluationResult(BaseModel):
    name: str
    action_correct: bool
    workflow_correct: bool
    tool_correct: bool
    schema_valid: bool
    latency_ms: float = Field(ge=0)
    actual_action_type: ActionType
    actual_workflow: WorkflowType | None = None
    actual_tool_name: ToolName | None = None

    @property
    def passed(self) -> bool:
        return (
            self.action_correct
            and self.workflow_correct
            and self.tool_correct
            and self.schema_valid
        )


class EvaluationReport(BaseModel):
    results: list[EvaluationResult]
    case_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    action_accuracy: float = Field(ge=0, le=1)
    workflow_accuracy: float = Field(ge=0, le=1)
    tool_accuracy: float = Field(ge=0, le=1)
    schema_validity_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
