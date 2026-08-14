from collections.abc import Mapping

from src.agents.context import ConversationContextBuilder
from src.agents.guardrails import AgentGuardrails, GuardrailViolationError
from src.agents.history import record_turn_history
from src.agents.repair import ConversationRepairHandler, DialogueActDetector
from src.agents.router import (
    AgentRouter,
    ToolResultRoutingError,
    UnsupportedIntentError,
)
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    LookupTripResult,
)
from src.agents.understanding.base import LanguageUnderstandingPort
from src.agents.understanding.factory import build_understanding_service
from src.agents.understanding.interpretation import TurnInterpretation
from src.agents.understanding.models import UnderstandingContext, UnderstandingIntent
from src.agents.understanding.rewrite_base import ContextualMessageRewriter
from src.agents.understanding.rewrite_factory import build_contextual_rewriter
from src.agents.understanding.rewrite_gate import ContextualRewriteGate
from src.agents.understanding.rewrite_models import RewriteResult
from src.agents.understanding.safety import enforce_raw_understanding_evidence
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.booking import RideBookingWorkflow
from src.agents.workflows.booking_models import BookingData
from src.agents.workflows.faq import FAQWorkflow
from src.agents.workflows.handoff import HandoffWorkflow
from src.agents.workflows.trip_lookup import TripLookupWorkflow
from src.agents.workflows.trip_lookup_models import TripLookupData


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
        dialogue_act_detector: DialogueActDetector | None = None,
        repair_handler: ConversationRepairHandler | None = None,
    ) -> None:
        self.router = router or AgentRouter()
        self.guardrails = guardrails or AgentGuardrails()
        self.understanding_service = understanding_service or build_understanding_service()
        self.context_builder = context_builder or ConversationContextBuilder()
        self.rewrite_gate = rewrite_gate or ContextualRewriteGate()
        self.message_rewriter = message_rewriter or build_contextual_rewriter()
        self.dialogue_act_detector = dialogue_act_detector or DialogueActDetector()
        self.repair_handler = repair_handler or ConversationRepairHandler()
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

        replay_action = self._completed_side_effect_replay(agent_input, current_state)
        if replay_action is not None:
            return self._validate_action(agent_input, current_state, replay_action)

        immediate_handoff = self.router.requires_immediate_handoff(
            agent_input,
            current_state,
        )
        if not immediate_handoff and agent_input.tool_result is None:
            command = self.dialogue_act_detector.detect(agent_input.transcript)
            repair_action = self.repair_handler.handle(
                command,
                agent_input,
                current_state,
            )
            if repair_action is not None:
                return self._validate_action(agent_input, current_state, repair_action)

        interpretation = None
        if not immediate_handoff:
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

        faq_interruption = None
        faq_requested_during_workflow = (
            understanding is not None
            and understanding.intent is UnderstandingIntent.FAQ
            and current_state.current_workflow in {WorkflowType.RIDE_BOOKING, WorkflowType.TRIP_LOOKUP}
        )
        if faq_requested_during_workflow and current_state.interrupted_workflow is not None:
            return self._validate_action(
                agent_input,
                current_state,
                self.repair_handler.nested_interruption_action(),
            )
        if faq_requested_during_workflow:
            faq_interruption = self.repair_handler.prepare_faq_interruption(current_state)

        try:
            workflow_type = (
                WorkflowType.FAQ
                if faq_interruption is not None
                else self.router.route(
                    agent_input,
                    current_state,
                    understanding,
                )
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
        if faq_interruption is not None:
            action = action.model_copy(
                update={
                    "state_updates": {
                        **action.state_updates,
                        "confirmation": ConfirmationStatus.NOT_REQUESTED,
                        "retry_count": 0,
                        "interrupted_workflow": faq_interruption,
                    }
                },
                deep=True,
            )
        elif (
            workflow_type is WorkflowType.FAQ
            and current_state.interrupted_workflow is not None
            and action.action_type is ActionType.RESPOND
            and action.state_updates.get("current_workflow") is None
        ):
            invitation = self.repair_handler.faq_resume_invitation(current_state)
            if invitation:
                action = action.model_copy(
                    update={"message": f"{action.message or ''} {invitation}".strip()},
                    deep=True,
                )
        return self._validate_action(agent_input, current_state, action)

    @staticmethod
    def _completed_side_effect_replay(
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction | None:
        result = agent_input.tool_result
        if (
            result is None
            or state.current_workflow is not None
            or state.pending_tool_name is not None
            or result.status is not ToolStatus.SUCCESS
        ):
            return None
        try:
            booking = BookingData.model_validate(state.collected_data.get("booking", {}))
            if result.tool_name is ToolName.CREATE_BOOKING and result.call_id == booking.completed_booking_call_id:
                payload = CreateBookingResult.model_validate(result.data)
                if payload.booking_id != booking.booking_id:
                    return None
                return AgentAction(
                    action_type=ActionType.RESPOND,
                    message="Chuyến xe này đã được đặt thành công trước đó.",
                    reason="An already completed create_booking result was replayed.",
                )
            if result.tool_name is ToolName.CANCEL_BOOKING and result.call_id == booking.completed_cancellation_call_id:
                payload = CancelBookingResult.model_validate(result.data)
                if payload.booking_id != booking.booking_id:
                    return None
                return AgentAction(
                    action_type=ActionType.RESPOND,
                    message="Chuyến xe này đã được hủy trước đó.",
                    reason="An already completed cancel_booking result was replayed.",
                )
            if result.tool_name is ToolName.LOOKUP_TRIP:
                trip = TripLookupData.model_validate(state.collected_data.get("trip_lookup", {}))
                if result.call_id != trip.completed_lookup_call_id:
                    return None
                payload = LookupTripResult.model_validate(result.data)
                replayed_ids = {match.booking_id for match in payload.trips} if payload.trips else {payload.booking_id}
                if trip.found_booking_id not in replayed_ids:
                    return None
                return AgentAction(
                    action_type=ActionType.RESPOND,
                    message="Kết quả này đã được xử lý trước đó; thông tin chuyến không thay đổi.",
                    reason="An already completed lookup_trip result was replayed.",
                )
        except ValueError:
            return None
        return None

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
        return state.current_workflow is WorkflowType.RIDE_BOOKING and state.current_step in {
            "CONFIRM",
            "CONFIRM_CANCEL",
        }

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
            if state.pending_tool_name in {
                ToolName.CREATE_BOOKING,
                ToolName.CANCEL_BOOKING,
                ToolName.CREATE_HANDOFF,
            }:
                validated = self.guardrails.safe_reconciliation_handoff(f"Guardrail violation: {exc}")
            else:
                validated = self.guardrails.safe_handoff(f"Guardrail violation: {exc}")
        return record_turn_history(agent_input, state, validated)


agent = LLMAgent()
