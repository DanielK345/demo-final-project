import pytest

from src.agents.graph import AgentGraphAdapter, agent
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


class RecordingAgent:
    def __init__(self) -> None:
        self.received_input: AgentInput | None = None
        self.received_state: AgentState | None = None

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState | None = None,
    ) -> AgentAction:
        self.received_input = agent_input
        self.received_state = state
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn đón ở đâu?",
            reason="Test response.",
        )


@pytest.mark.asyncio
async def test_agent_basic_flow():
    result = await agent.ainvoke({"query": "Hello"})
    assert "response" in result


@pytest.mark.asyncio
async def test_agent_state_structure():
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result


@pytest.mark.asyncio
async def test_graph_passes_conversation_state_to_agent():
    recording_agent = RecordingAgent()
    graph = AgentGraphAdapter(llm_agent=recording_agent)
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_PICKUP",
    )

    await graph.ainvoke(
        {
            "query": "Times City",
            "session_id": "session-001",
            "state": state.model_dump(mode="json"),
        }
    )

    assert recording_agent.received_input is not None
    assert recording_agent.received_input.session_id == "session-001"
    assert recording_agent.received_state == state


@pytest.mark.asyncio
async def test_graph_passes_tool_result_to_agent():
    recording_agent = RecordingAgent()
    graph = AgentGraphAdapter(llm_agent=recording_agent)
    tool_result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="session-001:search-pickup:1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    await graph.ainvoke(
        {
            "session_id": "session-001",
            "state": {
                "session_id": "session-001",
                "current_workflow": WorkflowType.RIDE_BOOKING,
                "current_step": "RESOLVE_PICKUP",
                "pending_tool_call_id": "session-001:search-pickup:1",
                "pending_tool_name": ToolName.SEARCH_PLACE,
            },
            "tool_result": tool_result.model_dump(mode="json"),
        }
    )

    assert recording_agent.received_input is not None
    assert recording_agent.received_input.transcript == ""
    assert recording_agent.received_input.tool_result == tool_result
