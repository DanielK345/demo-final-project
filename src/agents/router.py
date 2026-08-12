from src.agents.policy import AgentPolicy
from src.agents.schemas import AgentInput, WorkflowType
from src.agents.state import AgentState


class UnsupportedIntentError(ValueError):
    pass


class ToolResultRoutingError(ValueError):
    pass


class AgentRouter:
    """Minimal deterministic router used by the walking skeleton."""

    _BOOKING_TERMS = ("đặt xe", "gọi xe", "book", "ride")
    _LOOKUP_TERMS = ("tra cứu", "mã chuyến", "chuyến của tôi", "eta")
    _HANDOFF_TERMS = (
        "tổng đài viên",
        "người thật",
        "nhân viên hỗ trợ",
        "gặp nhân viên",
        "khiếu nại",
        "phàn nàn",
        "khẩn cấp",
        "nguy hiểm",
        "cứu tôi",
        "không cho tôi xuống xe",
        "tai nạn",
    )
    _FAQ_TERMS = ("dịch vụ", "giá", "thanh toán", "chính sách", "hoạt động")

    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    def route(self, agent_input: AgentInput, state: AgentState) -> WorkflowType:
        if self._requires_handoff(agent_input, state):
            return WorkflowType.HUMAN_HANDOFF

        if state.current_workflow is not None:
            return state.current_workflow

        if agent_input.tool_result is not None:
            raise ToolResultRoutingError(
                "Tool result cannot be routed without a current workflow"
            )

        return self.classify_intent(agent_input.transcript)

    def classify_intent(self, transcript: str) -> WorkflowType:
        normalized_transcript = transcript.casefold().strip()

        if any(term in normalized_transcript for term in self._HANDOFF_TERMS):
            return WorkflowType.HUMAN_HANDOFF
        if any(term in normalized_transcript for term in self._BOOKING_TERMS):
            return WorkflowType.RIDE_BOOKING
        if any(term in normalized_transcript for term in self._LOOKUP_TERMS):
            return WorkflowType.TRIP_LOOKUP
        if any(term in normalized_transcript for term in self._FAQ_TERMS):
            return WorkflowType.FAQ
        raise UnsupportedIntentError("No workflow matched the current input")

    def _requires_handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> bool:
        transcript = agent_input.transcript.casefold()
        explicit_handoff = any(term in transcript for term in self._HANDOFF_TERMS)
        retry_limit_reached = state.retry_count >= self.policy.max_retry_count
        low_confidence = (
            agent_input.stt_confidence is not None
            and agent_input.stt_confidence < self.policy.low_confidence_threshold
        )
        return explicit_handoff or retry_limit_reached or low_confidence
