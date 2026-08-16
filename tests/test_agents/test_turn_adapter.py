import pytest

from src.agents.contracts.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.contracts.state import AgentState
from src.agents.turn_adapter import AgentTurnAdapter


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
async def test_adapter_passes_conversation_state_to_agent():
    recording_agent = RecordingAgent()
    adapter = AgentTurnAdapter(llm_agent=recording_agent)
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_PICKUP",
    )

    result = await adapter.ainvoke(
        {
            "query": "Times City",
            "session_id": "session-001",
            "turn_id": "turn-001",
            "state": state.model_dump(mode="json"),
        }
    )

    assert recording_agent.received_input is not None
    assert recording_agent.received_input.session_id == "session-001"
    assert recording_agent.received_state == state
    assert result["response"] == "Bạn muốn đón ở đâu?"
    assert result["action"]["action_type"] == ActionType.ASK_USER


@pytest.mark.asyncio
async def test_adapter_passes_tool_result_to_agent():
    recording_agent = RecordingAgent()
    adapter = AgentTurnAdapter(llm_agent=recording_agent)
    tool_result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="session-001:search-pickup:1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )

    await adapter.ainvoke(
        {
            "session_id": "session-001",
            "turn_id": "turn-001",
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


@pytest.mark.asyncio
async def test_adapter_passes_stt_confidence_to_core_agent():
    recording_agent = RecordingAgent()
    adapter = AgentTurnAdapter(llm_agent=recording_agent)

    await adapter.ainvoke(
        {
            "query": "Tôi muốn đặt xe",
            "session_id": "session-001",
            "turn_id": "turn-001",
            "stt_confidence": 0.91,
        }
    )

    assert recording_agent.received_input is not None
    assert recording_agent.received_input.stt_confidence == 0.91


@pytest.mark.asyncio
async def test_adapter_preserves_input_fields():
    adapter = AgentTurnAdapter(llm_agent=RecordingAgent())

    result = await adapter.ainvoke(
        {
            "query": "Tôi muốn đặt xe",
            "session_id": "session-001",
            "turn_id": "turn-001",
            "request_id": "request-001",
        }
    )

    assert result["request_id"] == "request-001"
    assert result["action"]["action_type"] == ActionType.ASK_USER


@pytest.mark.asyncio
async def test_adapter_requires_backend_turn_id():
    adapter = AgentTurnAdapter(llm_agent=RecordingAgent())
    with pytest.raises(ValueError, match="turn_id is required"):
        await adapter.ainvoke({"query": "Hello"})
