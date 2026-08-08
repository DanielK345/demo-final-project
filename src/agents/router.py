from src.agents.schemas import AgentInput, WorkflowType
from src.agents.state import AgentState


class UnsupportedIntentError(ValueError):
    pass


class AgentRouter:
    """Minimal deterministic router used by the walking skeleton."""

    _BOOKING_TERMS = ("đặt xe", "gọi xe", "book", "ride")
    _LOOKUP_TERMS = ("tra cứu", "mã chuyến", "chuyến của tôi", "eta")
    _HANDOFF_TERMS = ("tổng đài viên", "người thật", "khiếu nại", "khẩn cấp")
    _FAQ_TERMS = ("dịch vụ", "giá", "thanh toán", "chính sách", "hoạt động")

    def route(self, agent_input: AgentInput, state: AgentState) -> WorkflowType:
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
