import pytest

from src.agents.agent import LLMAgent
from src.agents.schemas import ActionType, AgentInput, WorkflowType
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
    assert action.message == "Bạn muốn đón ở đâu?"
    assert action.state_updates == {
        "current_workflow": WorkflowType.RIDE_BOOKING,
        "current_step": "COLLECT_PICKUP",
    }


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

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_workflow"] is WorkflowType.RIDE_BOOKING
