from typing import Any

from pydantic import model_validator

from src.agents.schemas import ToolCall, ToolName
from src.agents.tools.base import BaseTool
from src.agents.tools.schemas import LookupTripParams


class ValidLookupTripParams(LookupTripParams):
    @model_validator(mode="after")
    def require_identifier(self) -> "ValidLookupTripParams":
        if not self.booking_id and not self.phone_number:
            raise ValueError("booking_id or phone_number is required")
        return self


class LookupTripTool(BaseTool):
    tool_name = ToolName.LOOKUP_TRIP

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = ValidLookupTripParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(exclude_none=True),
        )

