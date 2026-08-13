import pytest

from examples.core_agent_chat import (
    InteractiveSession,
    MockBackendExecutor,
    SessionTerminalStatus,
)
from src.agents.agent import LLMAgent
from src.agents.graph import AgentGraphAdapter
from src.agents.schemas import ActionType, ToolCall, ToolName
from src.agents.understanding.rewrite_service import PassthroughContextualRewriter
from src.agents.understanding.rules import RuleBasedUnderstanding


def test_mock_backend_returns_multiple_ho_guom_candidates():
    executor = MockBackendExecutor()
    call = ToolCall(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="call-1",
        params={"query": "khu vực Hồ Gươm"},
    )

    result = executor._result_data(call)

    assert len(result["candidates"]) == 2
    assert result["candidates"][1]["display_name"] == "Phố đi bộ Hồ Gươm"


@pytest.mark.parametrize("query", ["nhà", "về nhà tôi", "ở đó", "chỗ cũ"])
def test_mock_backend_does_not_invent_ambiguous_places(query):
    result = MockBackendExecutor()._result_data(
        ToolCall(
            tool_name=ToolName.SEARCH_PLACE,
            call_id="call-1",
            params={"query": query},
        )
    )

    assert result == {"candidates": []}


@pytest.mark.asyncio
async def test_interactive_session_keeps_state_and_executes_mock_tools(capsys):
    agent = LLMAgent(
        understanding_service=RuleBasedUnderstanding(),
        message_rewriter=PassthroughContextualRewriter(),
    )
    session = InteractiveSession(
        "interactive-test",
        graph=AgentGraphAdapter(agent),
    )

    started = await session.user_turn("Tôi muốn đặt xe")
    pickup = await session.user_turn("Times City")

    assert started[-1].action_type is ActionType.ASK_USER
    assert pickup[0].action_type is ActionType.CALL_TOOL
    assert pickup[-1].action_type is ActionType.ASK_USER
    assert session.state.current_workflow == "RIDE_BOOKING"
    assert session.state.current_step == "COLLECT_DESTINATION"
    assert len(session.state.conversation_history) == 5
    assert "MOCK BACKEND: search_place" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_interactive_handoff_is_terminal_until_reset():
    agent = LLMAgent(
        understanding_service=RuleBasedUnderstanding(),
        message_rewriter=PassthroughContextualRewriter(),
    )
    session = InteractiveSession(
        "interactive-test",
        graph=AgentGraphAdapter(agent),
    )

    actions = await session.user_turn("Tôi muốn gặp tổng đài viên")

    assert actions[-1].action_type is ActionType.HANDOFF
    assert session.terminal_status is SessionTerminalStatus.HANDOFF
    with pytest.raises(RuntimeError, match="dùng /reset"):
        await session.user_turn("Tôi muốn đặt xe")

    previous_session_id = session.session_id
    session.reset()

    assert session.session_id != previous_session_id
    assert session.terminal_status is SessionTerminalStatus.ACTIVE
    assert session.state.conversation_history == []
    assert session.turn_sequence == 0
