import pytest

from src.agents.agent import LLMAgent
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.understanding.models import UnderstandingResult
from src.agents.workflows.base import BaseWorkflow


class RecordingWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING

    def __init__(self) -> None:
        self.was_called = False
        self.received_input: AgentInput | None = None

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> AgentAction:
        del understanding
        self.was_called = True
        self.received_input = agent_input
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn đón ở đâu?",
            reason="Recording workflow handled the turn.",
        )


@pytest.mark.asyncio
async def test_agent_asks_for_clarification_on_unknown_intent():
    agent = LLMAgent()
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Xin chào bạn",
    )

    action = await agent.handle(agent_input)

    assert action.action_type is ActionType.ASK_USER
    assert action.message
    assert action.tool_call is None
    assert action.reason

@pytest.mark.asyncio
async def test_agent_rejects_state_from_another_session():
    agent = LLMAgent()
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Tôi muốn đặt xe",
    )
    state = AgentState(session_id="session-002")

    with pytest.raises(ValueError, match="same session"):
        await agent.handle(agent_input, state)


@pytest.mark.asyncio
async def test_agent_uses_injected_workflow_registry():
    workflow = RecordingWorkflow()
    agent = LLMAgent(
        workflows={
            WorkflowType.RIDE_BOOKING: workflow,
        }
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            transcript="Tôi muốn đặt xe",
        )
    )

    assert workflow.was_called is True
    assert action.action_type is ActionType.ASK_USER
    assert action.message == "Bạn muốn đón ở đâu?"


@pytest.mark.asyncio
async def test_agent_routes_tool_result_to_current_workflow():
    workflow = RecordingWorkflow()
    agent = LLMAgent(
        workflows={
            WorkflowType.RIDE_BOOKING: workflow,
        }
    )
    tool_result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="session-001:search-pickup:1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="RESOLVE_PICKUP",
        pending_tool_call_id="session-001:search-pickup:1",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    await agent.handle(
        AgentInput(
            session_id="session-001",
            tool_result=tool_result,
        ),
        state,
    )

    assert workflow.was_called is True
    assert workflow.received_input is not None
    assert workflow.received_input.tool_result is tool_result


@pytest.mark.asyncio
async def test_agent_handoffs_when_tool_result_has_no_current_workflow():
    tool_result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="session-001:search-pickup:1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            tool_result=tool_result,
        ),
        AgentState(session_id="session-001"),
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.message
    assert action.tool_call is None
    assert action.reason


@pytest.mark.asyncio
async def test_agent_handoffs_when_workflow_is_not_registered():
    agent = LLMAgent(workflows={})

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            transcript="Tôi muốn đặt xe",
        )
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.message
    assert action.tool_call is None
    assert action.state_updates["current_workflow"] is WorkflowType.HUMAN_HANDOFF
    assert action.state_updates["current_step"] == "HANDOFF_REQUIRED"
    assert action.state_updates["pending_tool_call_id"] is None
    assert action.state_updates["pending_tool_name"] is None
    assert action.reason
