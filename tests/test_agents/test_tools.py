import pytest
from pydantic import ValidationError

from src.agents.schemas import ActionType, AgentAction, ToolName, ToolResult, ToolStatus
from src.agents.tools.maps import SearchPlaceTool
from src.agents.tools.trip import LookupTripTool


def test_tool_builds_contract_without_executing_side_effect():
    call = SearchPlaceTool().build_call("call-001", query="Times City")

    assert call.tool_name == ToolName.SEARCH_PLACE
    assert call.params == {"query": "Times City"}


def test_trip_lookup_requires_an_identifier():
    with pytest.raises(ValidationError):
        LookupTripTool().build_call("call-002")


def test_call_tool_action_requires_tool_call():
    with pytest.raises(ValidationError):
        AgentAction(action_type=ActionType.CALL_TOOL)


def test_failed_tool_result_requires_error_details():
    with pytest.raises(ValidationError):
        ToolResult(
            tool_name=ToolName.LOOKUP_TRIP,
            call_id="call-003",
            status=ToolStatus.ERROR,
        )
