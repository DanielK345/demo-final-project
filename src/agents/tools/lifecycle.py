from typing import Any

from pydantic import BaseModel

from src.agents.contracts.schemas import ToolCall, ToolName, ToolResult, ToolStatus
from src.agents.contracts.state import AgentState
from src.agents.tools.schemas import (
    CancelBookingResult,
    CreateBookingResult,
    CreateHandoffResult,
    EstimateFareResult,
    GetVehicleOptionsResult,
    LookupTripResult,
    RetrieveKnowledgeResult,
    SearchPlaceResult,
)


class ToolLifecycleError(ValueError):
    pass


class UnexpectedToolResultError(ToolLifecycleError):
    pass


class ToolResultMismatchError(ToolLifecycleError):
    pass


class ToolResultPayloadError(ToolLifecycleError):
    pass


class ToolFailure(BaseModel):
    tool_name: ToolName
    call_id: str
    message: str
    code: str | None = None
    retryable: bool = False


ResultPayload = (
    SearchPlaceResult
    | EstimateFareResult
    | GetVehicleOptionsResult
    | CreateBookingResult
    | CancelBookingResult
    | LookupTripResult
    | RetrieveKnowledgeResult
    | CreateHandoffResult
)

_RESULT_MODELS: dict[ToolName, type[ResultPayload]] = {
    ToolName.SEARCH_PLACE: SearchPlaceResult,
    ToolName.ESTIMATE_FARE: EstimateFareResult,
    ToolName.GET_VEHICLE_OPTIONS: GetVehicleOptionsResult,
    ToolName.CREATE_BOOKING: CreateBookingResult,
    ToolName.CANCEL_BOOKING: CancelBookingResult,
    ToolName.LOOKUP_TRIP: LookupTripResult,
    ToolName.RETRIEVE_KNOWLEDGE: RetrieveKnowledgeResult,
    ToolName.CREATE_HANDOFF: CreateHandoffResult,
}


def pending_tool_updates(call: ToolCall, *, waiting_step: str) -> dict[str, Any]:
    if not waiting_step.strip():
        raise ValueError("waiting_step cannot be blank")
    return {
        "current_step": waiting_step,
        "pending_tool_call_id": call.call_id,
        "pending_tool_name": call.tool_name,
    }


def clear_pending_tool_updates() -> dict[str, None]:
    return {
        "pending_tool_call_id": None,
        "pending_tool_name": None,
    }


def correlate_tool_result(result: ToolResult, state: AgentState) -> None:
    if state.pending_tool_call_id is None or state.pending_tool_name is None:
        raise UnexpectedToolResultError("no tool result is currently pending")
    if result.call_id != state.pending_tool_call_id:
        raise ToolResultMismatchError(
            f"tool result call_id mismatch: expected {state.pending_tool_call_id}"
        )
    if result.tool_name is not state.pending_tool_name:
        raise ToolResultMismatchError(
            f"tool result name mismatch: expected {state.pending_tool_name.value}"
        )


def parse_tool_result(result: ToolResult, state: AgentState) -> ResultPayload:
    correlate_tool_result(result, state)
    if result.status is ToolStatus.ERROR:
        raise ToolResultPayloadError(
            "failed tool results must be handled with normalize_tool_failure"
        )

    model = _RESULT_MODELS[result.tool_name]
    try:
        return model.model_validate(result.data)
    except ValueError as exc:
        raise ToolResultPayloadError(
            f"invalid {result.tool_name.value} result payload"
        ) from exc


def normalize_tool_failure(result: ToolResult, state: AgentState) -> ToolFailure:
    correlate_tool_result(result, state)
    if result.status is not ToolStatus.ERROR or result.error is None:
        raise ToolResultPayloadError("tool result is not a failure")
    return ToolFailure(
        tool_name=result.tool_name,
        call_id=result.call_id,
        message=result.error,
        code=result.error_code,
        retryable=result.retryable,
    )
