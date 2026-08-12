from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.tools.call_id import build_call_id
from src.agents.tools.knowledge import RetrieveKnowledgeTool
from src.agents.tools.lifecycle import pending_tool_updates
from src.agents.workflows.base import BaseWorkflow


class FAQWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.FAQ

    async def handle(
        self, agent_input: AgentInput, state: AgentState
    ) -> AgentAction:
        call_id = build_call_id(
            session_id=agent_input.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.RETRIEVE_KNOWLEDGE,
            operation="faq",
            sequence=state.state_version + 1,
        )
        tool_call = RetrieveKnowledgeTool().build_call(
            call_id,
            query=agent_input.transcript,
        )
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates={
                "current_workflow": self.workflow_type,
                **pending_tool_updates(
                    tool_call,
                    waiting_step="WAITING_FOR_KNOWLEDGE",
                ),
            },
            reason="FAQ responses require grounded knowledge.",
        )
