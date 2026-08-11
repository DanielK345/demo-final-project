import pytest

from src.agents.router import AgentRouter, UnsupportedIntentError
from src.agents.schemas import (
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Tôi muốn đặt xe", WorkflowType.RIDE_BOOKING),
        ("Tra cứu chuyến của tôi", WorkflowType.TRIP_LOOKUP),
        ("Cho tôi gặp tổng đài viên", WorkflowType.HUMAN_HANDOFF),
        ("Dịch vụ hoạt động lúc nào?", WorkflowType.FAQ),
    ],
)
def test_router_selects_workflow(transcript: str, expected: WorkflowType):
    agent_input = AgentInput(session_id="session-001", transcript=transcript)
    state = AgentState(session_id="session-001")

    assert AgentRouter().route(agent_input, state) is expected


def test_router_continues_current_workflow():
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Tôi muốn hỏi về chính sách",
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="COLLECT_PICKUP",
    )

    result = AgentRouter().route(agent_input, state)

    assert result is WorkflowType.RIDE_BOOKING


def test_router_routes_tool_result_to_current_workflow():
    tool_result = ToolResult(
        tool_name=ToolName.SEARCH_PLACE,
        call_id="session-001:search-pickup:1",
        status=ToolStatus.SUCCESS,
        data={"candidates": []},
    )
    agent_input = AgentInput(
        session_id="session-001",
        tool_result=tool_result,
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="RESOLVE_PICKUP",
        pending_tool_call_id="session-001:search-pickup:1",
    )

    result = AgentRouter().route(agent_input, state)

    assert result is WorkflowType.RIDE_BOOKING


def test_router_rejects_unknown_intent():
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Xin chào bạn",
    )
    state = AgentState(session_id="session-001")

    with pytest.raises(UnsupportedIntentError):
        AgentRouter().route(agent_input, state)


def test_router_prioritizes_handoff_intent():
    agent_input = AgentInput(
        session_id="session-001",
        transcript="Tôi đang đặt xe nhưng muốn gặp tổng đài viên",
    )
    state = AgentState(session_id="session-001")

    result = AgentRouter().route(agent_input, state)

    assert result is WorkflowType.HUMAN_HANDOFF
