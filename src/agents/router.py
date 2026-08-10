from src.agents.schemas import AgentInput, WorkflowType
from src.agents.state import AgentState


class UnsupportedIntentError(ValueError):
    pass


class AgentRouter:
    """Minimal deterministic router used by the walking skeleton."""

    max_retry_count = 3
    low_confidence_threshold = 0.5

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

    def route(self, agent_input: AgentInput, state: AgentState) -> WorkflowType:
        if self._requires_handoff(agent_input, state):
            return WorkflowType.HUMAN_HANDOFF

        if state.current_workflow is not None:
            return state.current_workflow

        transcript = agent_input.transcript.casefold()
        if any(term in transcript for term in self._BOOKING_TERMS):
            return WorkflowType.RIDE_BOOKING
        if any(term in transcript for term in self._LOOKUP_TERMS):
            return WorkflowType.TRIP_LOOKUP
        if any(term in transcript for term in self._HANDOFF_TERMS):
            return WorkflowType.HUMAN_HANDOFF
        if any(term in transcript for term in self._FAQ_TERMS):
            return WorkflowType.FAQ

        raise UnsupportedIntentError("No workflow matched the current input")

    def _requires_handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> bool:
        transcript = agent_input.transcript.casefold()
        explicit_handoff = any(term in transcript for term in self._HANDOFF_TERMS)
        retry_limit_reached = state.retry_count >= self.max_retry_count
        low_confidence = (
            agent_input.stt_confidence is not None
            and agent_input.stt_confidence < self.low_confidence_threshold
        )
        return explicit_handoff or retry_limit_reached or low_confidence
