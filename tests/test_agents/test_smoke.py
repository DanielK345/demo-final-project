import pytest

from src.agents.agent import LLMAgent
from src.agents.schemas import ActionType, AgentInput, ToolName, WorkflowType
from src.agents.state import AgentState


@pytest.mark.asyncio
async def test_ride_booking_walking_skeleton():
    agent = LLMAgent()
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Tôi muốn đặt xe",
        stt_confidence=0.98,
    )

    action = await agent.handle(agent_input)

    assert action.action_type is ActionType.ASK_USER
    assert "điểm đón" in action.message
    assert action.state_updates["current_workflow"] is WorkflowType.RIDE_BOOKING
    assert action.state_updates["current_step"] == "COLLECT_PICKUP"
    assert "booking" in action.state_updates["collected_data"]


@pytest.mark.asyncio
async def test_agent_continues_the_active_workflow():
    agent = LLMAgent()
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_PICKUP",
    )

    action = await agent.handle(
        AgentInput(session_id="session-001", transcript="Times City"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert action.tool_call.params == {"query": "Times City"}
    assert action.state_updates["current_workflow"] is WorkflowType.RIDE_BOOKING
