import pytest
from pydantic import ValidationError

from src.agents.state import AgentState


def test_state_updates_are_validated():
    state = AgentState(session_id="session-001")

    with pytest.raises(ValidationError):
        state.apply({"retry_count": -1})
