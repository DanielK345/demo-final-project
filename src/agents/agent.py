from collections.abc import Mapping

from src.agents.guardrails import AgentGuardrails, GuardrailViolationError
from src.agents.router import (
    AgentRouter,
    ToolResultRoutingError,
    UnsupportedIntentError,
)
from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.understanding.base import LanguageUnderstandingPort
from src.agents.understanding.factory import build_understanding_service
from src.agents.understanding.models import UnderstandingContext, UnderstandingResult
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
    ) -> None:
        self.router = router or AgentRouter()
        self.guardrails = guardrails or AgentGuardrails()
        self.understanding_service = (
            understanding_service or build_understanding_service()
        )
        default_workflows = {
            WorkflowType.RIDE_BOOKING: RideBookingWorkflow(),
            WorkflowType.TRIP_LOOKUP: TripLookupWorkflow(),
            WorkflowType.FAQ: FAQWorkflow(),
            WorkflowType.HUMAN_HANDOFF: HandoffWorkflow(),
        }
        self.workflows = dict(
            default_workflows if workflows is None else workflows
        )

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState | None = None,
    ) -> AgentAction:
        current_state = state or AgentState(session_id=agent_input.session_id)
        if current_state.session_id != agent_input.session_id:
            raise ValueError("agent input and state must belong to the same session")

        understanding = None
        if not self.router.requires_immediate_handoff(agent_input, current_state):
            understanding = await self._understand(agent_input, current_state)

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
                self.guardrails.safe_handoff(
                    f"Workflow is not registered: {workflow_type}"
                ),
            )
        action = await workflow.handle(
            agent_input,
            current_state,
            understanding,
        )
        return self._validate_action(agent_input, current_state, action)

    async def _understand(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> UnderstandingResult | None:
        if not agent_input.transcript.strip():
            return None
        known_fields = self._known_fields(state.collected_data)
        return await self.understanding_service.understand(
            agent_input.transcript,
            UnderstandingContext(
                session_id=state.session_id,
                current_workflow=state.current_workflow,
                current_step=state.current_step,
                known_fields=known_fields,
            ),
        )

    @staticmethod
    def _known_fields(collected_data: dict) -> list[str]:
        fields: list[str] = []
        for namespace, value in collected_data.items():
            if isinstance(value, dict):
                fields.extend(
                    f"{namespace}.{key}"
                    for key, item in value.items()
                    if item not in (None, "", [], {})
                )
            elif value not in (None, "", [], {}):
                fields.append(namespace)
        return sorted(fields)

    def _validate_action(
        self,
        agent_input: AgentInput,
        state: AgentState,
        action: AgentAction,
    ) -> AgentAction:
        try:
            return self.guardrails.validate_and_sanitize(agent_input, state, action)
        except GuardrailViolationError as exc:
            return self.guardrails.safe_handoff(f"Guardrail violation: {exc}")


agent = LLMAgent()
