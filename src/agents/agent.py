from collections.abc import Mapping

from src.agents.router import AgentRouter, UnsupportedIntentError
from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
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
    ) -> None:
        self.router = router or AgentRouter()
        self.workflows = dict(
            workflows
            or {
                WorkflowType.RIDE_BOOKING: RideBookingWorkflow(),
                WorkflowType.TRIP_LOOKUP: TripLookupWorkflow(),
                WorkflowType.FAQ: FAQWorkflow(),
                WorkflowType.HUMAN_HANDOFF: HandoffWorkflow(),
            }
        )

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState | None = None,
    ) -> AgentAction:
        current_state = state or AgentState(session_id=agent_input.session_id)
        if current_state.session_id != agent_input.session_id:
            raise ValueError("agent input and state must belong to the same session")

        try:
            workflow_type = self.router.route(agent_input, current_state)
        except UnsupportedIntentError:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn cần đặt xe, tra cứu chuyến đi hay hỗ trợ vấn đề khác?",
                reason="The user's intent is not clear enough to select a workflow.",
            )

        workflow = self.workflows.get(workflow_type)
        if workflow is None:
            raise LookupError(f"Workflow is not registered: {workflow_type}")
        return await workflow.handle(agent_input, current_state)


agent = LLMAgent()
