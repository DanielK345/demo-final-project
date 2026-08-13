from collections.abc import Mapping

from src.agents.context import ConversationContextBuilder
from src.agents.guardrails import AgentGuardrails, GuardrailViolationError
from src.agents.history import record_turn_history
from src.agents.router import (
    AgentRouter,
    ToolResultRoutingError,
    UnsupportedIntentError,
)
from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.understanding.base import LanguageUnderstandingPort
from src.agents.understanding.factory import build_understanding_service
from src.agents.understanding.interpretation import TurnInterpretation
from src.agents.understanding.models import UnderstandingContext
from src.agents.understanding.rewrite_base import ContextualMessageRewriter
from src.agents.understanding.rewrite_factory import build_contextual_rewriter
from src.agents.understanding.rewrite_gate import ContextualRewriteGate
from src.agents.understanding.rewrite_models import RewriteResult
from src.agents.understanding.safety import enforce_raw_understanding_evidence
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking import RideBookingWorkflow
from src.agents.workflows.faq import FAQWorkflow
from src.agents.workflows.handoff import HandoffWorkflow
from src.agents.workflows.trip_lookup import TripLookupWorkflow


class LLMAgent:
    """Application entrypoint for one conversation turn."""

    def __init__(
        self,
        router: AgentRouter | None = None,
        workflows: Mapping[WorkflowType, BaseWorkflow] | None = None,
        guardrails: AgentGuardrails | None = None,
        understanding_service: LanguageUnderstandingPort | None = None,
        context_builder: ConversationContextBuilder | None = None,
        rewrite_gate: ContextualRewriteGate | None = None,
        message_rewriter: ContextualMessageRewriter | None = None,
    ) -> None:
        self.router = router or AgentRouter()
        self.guardrails = guardrails or AgentGuardrails()
        self.understanding_service = understanding_service or build_understanding_service()
        self.context_builder = context_builder or ConversationContextBuilder()
        self.rewrite_gate = rewrite_gate or ContextualRewriteGate()
        self.message_rewriter = message_rewriter or build_contextual_rewriter()
        default_workflows = {
            WorkflowType.RIDE_BOOKING: RideBookingWorkflow(),
            WorkflowType.TRIP_LOOKUP: TripLookupWorkflow(),
            WorkflowType.FAQ: FAQWorkflow(),
            WorkflowType.HUMAN_HANDOFF: HandoffWorkflow(),
        }
        self.workflows = dict(default_workflows if workflows is None else workflows)

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState | None = None,
    ) -> AgentAction:
        current_state = state or AgentState(session_id=agent_input.session_id)
        if current_state.session_id != agent_input.session_id:
            raise ValueError("agent input and state must belong to the same session")

        interpretation = None
        if not self.router.requires_immediate_handoff(agent_input, current_state):
            interpretation = await self._understand(agent_input, current_state)
        understanding = interpretation.understanding if interpretation else None
        workflow_text = agent_input.transcript
        if interpretation and not self._requires_raw_workflow_text(current_state):
            workflow_text = interpretation.effective_text
        workflow_input = (
            agent_input.model_copy(
                update={"transcript": workflow_text},
                deep=True,
            )
            if interpretation
            else agent_input
        )

        try:
            workflow_type = self.router.route(
                agent_input,
                current_state,
                understanding,
            )
        except UnsupportedIntentError:
            action = AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn cần đặt xe, tra cứu chuyến đi hay hỗ trợ vấn đề khác?",
                reason="The user's intent is not clear enough to select a workflow.",
            )
            return self._validate_action(agent_input, current_state, action)
        except ToolResultRoutingError as exc:
            return self._validate_action(
                agent_input,
                current_state,
                self.guardrails.safe_handoff(str(exc)),
            )

        workflow = self.workflows.get(workflow_type)
        if workflow is None:
            return self._validate_action(
                agent_input,
                current_state,
                self.guardrails.safe_handoff(f"Workflow is not registered: {workflow_type}"),
            )
        action = await workflow.handle(
            workflow_input,
            current_state,
            understanding,
        )
        return self._validate_action(agent_input, current_state, action)

    async def _understand(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> TurnInterpretation | None:
        if agent_input.tool_result is not None or not agent_input.transcript.strip():
            return None
        context = self.context_builder.build(agent_input, state)
        decision = self.rewrite_gate.evaluate(agent_input.transcript, context)
        rewrite = (
            await self.message_rewriter.rewrite(
                agent_input.transcript,
                context,
                decision,
            )
            if decision.should_rewrite
            else RewriteResult.unchanged(agent_input.transcript)
        )
        understanding = await self.understanding_service.understand(
            rewrite.rewritten_text,
            UnderstandingContext(
                session_id=state.session_id,
                current_workflow=context.current_workflow,
                current_step=context.current_step,
                known_fields=context.known_fields,
                business_snapshot=context.business_snapshot,
                available_candidates=context.available_candidates,
                recent_messages=context.recent_messages,
                conversation_summary=context.conversation_summary,
                rewrite_applied=rewrite.changed,
                rewrite_evidence=rewrite.resolved_references,
                rewrite_ambiguities=rewrite.ambiguities,
            ),
        )
        understanding = enforce_raw_understanding_evidence(
            understanding,
            raw_transcript=agent_input.transcript,
        )
        return TurnInterpretation(
            context=context,
            rewrite_decision=decision,
            rewrite_result=rewrite,
            understanding=understanding,
        )

    @staticmethod
    def _requires_raw_workflow_text(state: AgentState) -> bool:
        return state.current_workflow is WorkflowType.RIDE_BOOKING and state.current_step == "CONFIRM"

    def _validate_action(
        self,
        agent_input: AgentInput,
        state: AgentState,
        action: AgentAction,
    ) -> AgentAction:
        try:
            validated = self.guardrails.validate_and_sanitize(
                agent_input,
                state,
                action,
            )
        except GuardrailViolationError as exc:
            validated = self.guardrails.safe_handoff(f"Guardrail violation: {exc}")
        return record_turn_history(agent_input, state, validated)


agent = LLMAgent()
