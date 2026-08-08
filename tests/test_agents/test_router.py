import pytest

from src.agents.router import AgentRouter
from src.agents.schemas import AgentInput, WorkflowType
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
