from dataclasses import dataclass
from enum import StrEnum

from src.agents.contracts.schemas import ToolName, ToolResult
from src.agents.contracts.state import AgentState
from src.agents.core.booking.state import BookingData, BookingStep
from src.agents.core.policy import AgentPolicy
from src.agents.tools.lifecycle import normalize_tool_failure


class BookingToolFailureKind(StrEnum):
    RETRY_PICKUP = "RETRY_PICKUP"
    RETRY_DESTINATION = "RETRY_DESTINATION"
    RETRY_FARE = "RETRY_FARE"
    RETRY_VEHICLE_OPTIONS = "RETRY_VEHICLE_OPTIONS"
    RECONCILE = "RECONCILE"
    CONFIRM_BOOKING_RETRY = "CONFIRM_BOOKING_RETRY"
    CONFIRM_CANCELLATION_RETRY = "CONFIRM_CANCELLATION_RETRY"
    HANDOFF = "HANDOFF"


@dataclass(frozen=True)
class BookingToolFailurePlan:
    kind: BookingToolFailureKind
    reason: str
    retry_count: int


def plan_booking_tool_failure(
    result: ToolResult,
    state: AgentState,
    data: BookingData,
    policy: AgentPolicy,
) -> BookingToolFailurePlan:
    failure = normalize_tool_failure(result, state)
    next_retry = state.retry_count + 1
    can_retry = failure.retryable and next_retry < policy.retry_limit(result.tool_name)

    if result.tool_name is ToolName.SEARCH_PLACE and can_retry:
        kind = (
            BookingToolFailureKind.RETRY_PICKUP
            if state.current_step == BookingStep.WAITING_FOR_PICKUP_RESULT
            else BookingToolFailureKind.RETRY_DESTINATION
        )
        query = data.pickup_query if kind is BookingToolFailureKind.RETRY_PICKUP else data.destination_query
        if query:
            return BookingToolFailurePlan(kind, failure.message, next_retry)

    if result.tool_name is ToolName.ESTIMATE_FARE and can_retry:
        return BookingToolFailurePlan(
            BookingToolFailureKind.RETRY_FARE,
            failure.message,
            next_retry,
        )
    if result.tool_name is ToolName.GET_VEHICLE_OPTIONS and can_retry:
        return BookingToolFailurePlan(
            BookingToolFailureKind.RETRY_VEHICLE_OPTIONS,
            failure.message,
            next_retry,
        )

    uncertain_outcome = failure.retryable or (failure.code or "").casefold() in {
        "timeout",
        "unknown_outcome",
        "connection_lost",
    }
    if result.tool_name in {ToolName.CREATE_BOOKING, ToolName.CANCEL_BOOKING} and uncertain_outcome:
        return BookingToolFailurePlan(
            BookingToolFailureKind.RECONCILE,
            f"Unknown {result.tool_name.value} outcome: {failure.message}",
            next_retry,
        )
    if result.tool_name is ToolName.CREATE_BOOKING:
        return BookingToolFailurePlan(
            BookingToolFailureKind.CONFIRM_BOOKING_RETRY,
            f"Booking failed definitively: {failure.message}",
            next_retry,
        )
    if result.tool_name is ToolName.CANCEL_BOOKING:
        return BookingToolFailurePlan(
            BookingToolFailureKind.CONFIRM_CANCELLATION_RETRY,
            f"Cancellation failed definitively: {failure.message}",
            next_retry,
        )
    return BookingToolFailurePlan(
        BookingToolFailureKind.HANDOFF,
        f"Critical tool error: {failure.message}",
        next_retry,
    )
