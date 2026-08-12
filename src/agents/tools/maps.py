from typing import Any

from src.agents.schemas import ToolCall, ToolName
from src.agents.tools.base import BaseTool
from src.agents.tools.schemas import SearchPlaceParams


class SearchPlaceTool(BaseTool):
    tool_name = ToolName.SEARCH_PLACE

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = SearchPlaceParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(),
        )
