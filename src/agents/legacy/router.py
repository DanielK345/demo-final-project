from src.agents.contracts.schemas import AgentInput, WorkflowType
from src.agents.contracts.state import AgentState
from src.agents.core.policy import AgentPolicy
from src.agents.legacy.understanding.models import UnderstandingIntent, UnderstandingResult


class UnsupportedIntentError(ValueError):
    pass


class ToolResultRoutingError(ValueError):
    pass


class AgentRouter:
    """Minimal deterministic router used by the walking skeleton."""

    _BOOKING_TERMS = ("đặt xe", "gọi xe", "book", "ride")
    _LOOKUP_TERMS = (
        "tra cứu",
        "mã chuyến",
        "chuyến của tôi",
        "xe của tôi",
        "xe tới đâu",
        "xe đến đâu",
        "còn bao lâu",
        "tài xế tới đâu",
        "eta",
    )
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

    def route(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> WorkflowType:
        if self.requires_immediate_handoff(agent_input, state):
            return WorkflowType.HUMAN_HANDOFF

        if (
            understanding is not None
            and understanding.intent is UnderstandingIntent.HUMAN_HANDOFF
        ):
            return WorkflowType.HUMAN_HANDOFF

        if state.current_workflow is not None:
            return state.current_workflow

        if agent_input.tool_result is not None:
            raise ToolResultRoutingError(
                "Tool result cannot be routed without a current workflow"
            )

        if understanding is not None:
            workflow = self._workflow_from_understanding(understanding.intent)
            if workflow is not None:
                return workflow
        if self._is_faq_follow_up(agent_input.transcript, state):
            return WorkflowType.FAQ
        return self.classify_intent(agent_input.transcript)

    @staticmethod
    def _is_faq_follow_up(transcript: str, state: AgentState) -> bool:
        faq = state.collected_data.get("faq")
        if not isinstance(faq, dict) or not faq.get("answer"):
            return False
        normalized = " ".join(transcript.casefold().split())
        return any(
            normalized.startswith(prefix)
            for prefix in (
                "còn ",
                "thế còn ",
                "vậy còn ",
                "trường hợp đó",
                "cái đó",
            )
        )

    @staticmethod
    def _workflow_from_understanding(
        intent: UnderstandingIntent,
    ) -> WorkflowType | None:
        mapping = {
            UnderstandingIntent.RIDE_BOOKING: WorkflowType.RIDE_BOOKING,
            UnderstandingIntent.TRIP_LOOKUP: WorkflowType.TRIP_LOOKUP,
            UnderstandingIntent.FAQ: WorkflowType.FAQ,
            UnderstandingIntent.HUMAN_HANDOFF: WorkflowType.HUMAN_HANDOFF,
        }
        return mapping.get(intent)

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

    def requires_immediate_handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> bool:
        # A callback must first be correlated and processed by its owning workflow.
        # Any transcript delivered with it is handled in a later input turn.
        if agent_input.tool_result is not None:
            return False
        transcript = agent_input.transcript.casefold()
        explicit_handoff = any(term in transcript for term in self._HANDOFF_TERMS)
        retry_limit_reached = (
            state.current_workflow is None
            and state.retry_count >= self.policy.max_retry_count
        )
        low_confidence = (
            bool(agent_input.transcript.strip())
            and agent_input.stt_confidence is not None
            and agent_input.stt_confidence < self.policy.low_confidence_threshold
        )
        return explicit_handoff or retry_limit_reached or low_confidence
