from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolCall,
    ToolName,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.workflows.base import BaseWorkflow


class FAQWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.FAQ

    async def handle(
        self, agent_input: AgentInput, state: AgentState
    ) -> AgentAction:
        call_id = f"{agent_input.session_id}:knowledge"
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=ToolCall(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=call_id,
                params={"query": agent_input.transcript},
            ),
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "WAITING_FOR_KNOWLEDGE",
                "pending_tool_call_id": call_id,
                "pending_tool_name": ToolName.RETRIEVE_KNOWLEDGE,
            },
            reason="FAQ responses require grounded knowledge.",
        )
