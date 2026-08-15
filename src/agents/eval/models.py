from pydantic import BaseModel, Field, model_validator

from src.agents.contracts.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.contracts.state import AgentState


class EvaluationCase(BaseModel):
    name: str = Field(min_length=1)
    agent_input: AgentInput
    state: AgentState | None = None
    expected_action_type: ActionType
    expected_workflow: WorkflowType | None = None
    expected_tool_name: ToolName | None = None

    @model_validator(mode="after")
    def validate_expected_tool(self) -> "EvaluationCase":
        if self.expected_action_type is ActionType.CALL_TOOL and self.expected_tool_name is None:
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
        return self.action_correct and self.workflow_correct and self.tool_correct and self.schema_valid


class EvaluationReport(BaseModel):
    results: list[EvaluationResult]
    case_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    action_accuracy: float = Field(ge=0, le=1)
    workflow_accuracy: float = Field(ge=0, le=1)
    tool_accuracy: float = Field(ge=0, le=1)
    schema_validity_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    p50_latency_ms: float = Field(default=0, ge=0)
    p95_latency_ms: float = Field(default=0, ge=0)
    p99_latency_ms: float = Field(default=0, ge=0)


class EvaluationTurn(BaseModel):
    transcript: str = ""
    stt_confidence: float | None = Field(default=None, ge=0, le=1)
    tool_name: ToolName | None = None
    tool_status: ToolStatus = ToolStatus.SUCCESS
    tool_data: dict = Field(default_factory=dict)
    tool_error: str | None = None
    tool_error_code: str | None = None
    retryable: bool = False
    expected_action_type: ActionType
    expected_workflow: WorkflowType | None = None
    expected_tool_name: ToolName | None = None
    expected_tool_params: dict = Field(default_factory=dict)
    forbidden_message_terms: list[str] = Field(default_factory=list)

    def to_agent_input(
        self,
        *,
        session_id: str,
        turn_id: str,
        pending_call_id: str | None,
    ) -> AgentInput:
        result = None
        if self.tool_name is not None:
            if pending_call_id is None:
                raise ValueError("tool evaluation turn requires a pending call")
            result = ToolResult(
                tool_name=self.tool_name,
                call_id=pending_call_id,
                status=self.tool_status,
                data=self.tool_data,
                error=self.tool_error,
                error_code=self.tool_error_code,
                retryable=self.retryable,
            )
        return AgentInput(
            session_id=session_id,
            turn_id=turn_id,
            transcript=self.transcript,
            stt_confidence=self.stt_confidence,
            tool_result=result,
        )


class ConversationEvaluationCase(BaseModel):
    name: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    initial_state: AgentState | None = None
    turns: list[EvaluationTurn] = Field(min_length=1)
    expect_completion: bool = False

    @model_validator(mode="after")
    def validate_session(self) -> "ConversationEvaluationCase":
        if self.initial_state and self.initial_state.session_id != self.session_id:
            raise ValueError("evaluation state must match scenario session")
        return self


class ConversationEvaluationResult(BaseModel):
    name: str
    turn_count: int = Field(ge=0)
    passed_turns: int = Field(ge=0)
    action_accuracy: float = Field(ge=0, le=1)
    tool_accuracy: float = Field(ge=0, le=1)
    tool_argument_accuracy: float = Field(ge=0, le=1)
    pii_leak_count: int = Field(ge=0)
    confirmation_safety_violations: int = Field(ge=0)
    duplicate_side_effect_violations: int = Field(ge=0)
    completed: bool
    completion_expected: bool = False
    latency_ms: list[float] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.passed_turns == self.turn_count
            and (not self.completion_expected or self.completed)
            and self.pii_leak_count == 0
            and self.confirmation_safety_violations == 0
            and self.duplicate_side_effect_violations == 0
        )


class ReadinessThresholds(BaseModel):
    minimum_pass_rate: float = Field(default=0.95, ge=0, le=1)
    minimum_action_accuracy: float = Field(default=0.95, ge=0, le=1)
    minimum_tool_accuracy: float = Field(default=0.98, ge=0, le=1)
    minimum_tool_argument_accuracy: float = Field(default=0.98, ge=0, le=1)
    minimum_workflow_completion_rate: float = Field(default=1.0, ge=0, le=1)
    maximum_p95_latency_ms: float | None = Field(default=None, ge=0)


class ReadinessReport(BaseModel):
    dataset_version: str
    scenario_count: int = Field(ge=0)
    turn_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    action_accuracy: float = Field(ge=0, le=1)
    tool_accuracy: float = Field(ge=0, le=1)
    tool_argument_accuracy: float = Field(ge=0, le=1)
    workflow_completion_rate: float = Field(ge=0, le=1)
    pii_leakage_rate: float = Field(ge=0, le=1)
    confirmation_safety_violation_rate: float = Field(ge=0, le=1)
    duplicate_side_effect_violation_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    p99_latency_ms: float = Field(ge=0)
    ready: bool
    failed_gates: list[str] = Field(default_factory=list)
    scenarios: list[ConversationEvaluationResult] = Field(default_factory=list)
