from src.agents.schemas import ActionType, AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.workflows.base import BaseWorkflow


class HandoffWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.HUMAN_HANDOFF

    async def handle(
        self, agent_input: AgentInput, state: AgentState
    ) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message="Tôi sẽ chuyển bạn tới tổng đài viên.",
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "HANDOFF_REQUESTED",
            },
            reason="The conversation requires a human agent.",
        )

