from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.workflows.base import BaseWorkflow


class RideBookingWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction:
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn đón ở đâu?",
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "COLLECT_PICKUP",
            },
            reason="Ride booking requires a pickup location.",
        )

