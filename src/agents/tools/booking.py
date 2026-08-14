from typing import Any

from src.agents.schemas import ToolCall, ToolName
from src.agents.tools.base import BaseTool
from src.agents.tools.schemas import (
    CancelBookingParams,
    CreateBookingParams,
    EstimateFareParams,
    GetVehicleOptionsParams,
)


class CreateBookingTool(BaseTool):
    tool_name = ToolName.CREATE_BOOKING

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = CreateBookingParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(mode="json", exclude_none=True),
        )


class EstimateFareTool(BaseTool):
    tool_name = ToolName.ESTIMATE_FARE

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = EstimateFareParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(mode="json"),
        )


class GetVehicleOptionsTool(BaseTool):
    tool_name = ToolName.GET_VEHICLE_OPTIONS

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = GetVehicleOptionsParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(mode="json", exclude_none=True),
        )


class CancelBookingTool(BaseTool):
    tool_name = ToolName.CANCEL_BOOKING

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = CancelBookingParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(),
        )
