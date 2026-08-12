from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.workflows.base import BaseWorkflow


class TripLookupWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.TRIP_LOOKUP

    async def handle(
        self, agent_input: AgentInput, state: AgentState
    ) -> AgentAction:
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn vui lòng cung cấp mã chuyến hoặc số điện thoại đặt xe.",
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "COLLECT_LOOKUP_IDENTIFIER",
            },
            reason="A trip identifier is required before lookup.",
        )

