"""Typed ToolCall builders.

These classes only validate and describe backend work. They never execute I/O.
"""

from typing import Any

from src.agents.contracts.schemas import ToolCall, ToolName
from src.agents.tools.schemas import (
    CancelBookingParams,
    CreateBookingParams,
    CreateHandoffParams,
    EstimateFareParams,
    GetVehicleOptionsParams,
    LookupTripParams,
    RetrieveKnowledgeParams,
    SearchPlaceParams,
)


class ToolCallBuilder:
    tool_name: ToolName
    params_model: type
    exclude_none = False

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = self.params_model.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(mode="json", exclude_none=self.exclude_none),
        )


class SearchPlaceTool(ToolCallBuilder):
    tool_name = ToolName.SEARCH_PLACE
    params_model = SearchPlaceParams


class GetVehicleOptionsTool(ToolCallBuilder):
    tool_name = ToolName.GET_VEHICLE_OPTIONS
    params_model = GetVehicleOptionsParams
    exclude_none = True


class EstimateFareTool(ToolCallBuilder):
    tool_name = ToolName.ESTIMATE_FARE
    params_model = EstimateFareParams


class CreateBookingTool(ToolCallBuilder):
    tool_name = ToolName.CREATE_BOOKING
    params_model = CreateBookingParams
    exclude_none = True


class CancelBookingTool(ToolCallBuilder):
    tool_name = ToolName.CANCEL_BOOKING
    params_model = CancelBookingParams


class LookupTripTool(ToolCallBuilder):
    tool_name = ToolName.LOOKUP_TRIP
    params_model = LookupTripParams
    exclude_none = True


class RetrieveKnowledgeTool(ToolCallBuilder):
    tool_name = ToolName.RETRIEVE_KNOWLEDGE
    params_model = RetrieveKnowledgeParams


class CreateHandoffTool(ToolCallBuilder):
    tool_name = ToolName.CREATE_HANDOFF
    params_model = CreateHandoffParams
