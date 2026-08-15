import re

from pydantic import ValidationError

from src.agents.contracts.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    WorkflowType,
)
from src.agents.contracts.state import AgentState, ConfirmationStatus
from src.agents.core.policy import AgentPolicy
from src.agents.tools.lifecycle import clear_pending_tool_updates
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

_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)")
_BOOKING_ID_PATTERN = re.compile(
    r"(?i)(\b(?:booking(?:\s*id)?|mã\s+(?:chuyến|đặt\s*xe))\s*[=:#!-]?\s*)"
    r"[A-Za-z0-9][A-Za-z0-9_-]{2,}"
)
_AGENT_MANAGED_STATE_FIELDS = {
    "conversation_history",
    "conversation_summary",
    "tool_call_count",
}
_SIDE_EFFECT_TOOLS = {
    ToolName.CREATE_BOOKING,
    ToolName.CANCEL_BOOKING,
    ToolName.CREATE_HANDOFF,
}
_WORKFLOW_TOOLS = {
    WorkflowType.RIDE_BOOKING: {
        ToolName.SEARCH_PLACE,
        ToolName.GET_VEHICLE_OPTIONS,
        ToolName.ESTIMATE_FARE,
        ToolName.CREATE_BOOKING,
        ToolName.CANCEL_BOOKING,
    },
    WorkflowType.TRIP_LOOKUP: {ToolName.LOOKUP_TRIP},
    WorkflowType.FAQ: {ToolName.RETRIEVE_KNOWLEDGE},
    WorkflowType.HUMAN_HANDOFF: {ToolName.CREATE_HANDOFF},
}
_TOOL_PARAM_MODELS = {
    ToolName.SEARCH_PLACE: SearchPlaceParams,
    ToolName.GET_VEHICLE_OPTIONS: GetVehicleOptionsParams,
    ToolName.ESTIMATE_FARE: EstimateFareParams,
    ToolName.CREATE_BOOKING: CreateBookingParams,
    ToolName.CANCEL_BOOKING: CancelBookingParams,
    ToolName.LOOKUP_TRIP: LookupTripParams,
    ToolName.RETRIEVE_KNOWLEDGE: RetrieveKnowledgeParams,
    ToolName.CREATE_HANDOFF: CreateHandoffParams,
}


class GuardrailViolationError(ValueError):
    pass


class AgentGuardrails:
    def __init__(self, policy: AgentPolicy | None = None) -> None:
        self.policy = policy or AgentPolicy()

    def validate_and_sanitize(
        self,
        agent_input: AgentInput,
        state: AgentState,
        action: AgentAction,
    ) -> AgentAction:
        updates = dict(action.state_updates)
        managed_updates = _AGENT_MANAGED_STATE_FIELDS.intersection(updates)
        if managed_updates:
            fields = ", ".join(sorted(managed_updates))
            raise GuardrailViolationError(f"workflow cannot modify agent-managed state fields: {fields}")
        if agent_input.stt_confidence is not None:
            updates["last_stt_confidence"] = agent_input.stt_confidence

        try:
            next_state = state.apply(updates)
        except (ValidationError, ValueError) as exc:
            raise GuardrailViolationError("action contains invalid state updates") from exc

        if action.message and len(action.message) > self.policy.max_spoken_message_characters:
            raise GuardrailViolationError("spoken message exceeds the configured limit")

        pending_side_effect_changed = state.pending_tool_name in _SIDE_EFFECT_TOOLS and (
            next_state.pending_tool_call_id != state.pending_tool_call_id
            or next_state.pending_tool_name is not state.pending_tool_name
        )
        result_matches_pending = (
            agent_input.tool_result is not None
            and agent_input.tool_result.call_id == state.pending_tool_call_id
            and agent_input.tool_result.tool_name is state.pending_tool_name
        )
        if pending_side_effect_changed and not result_matches_pending:
            raise GuardrailViolationError("cannot clear an unresolved side effect without its tool result")

        if action.action_type is ActionType.END_SESSION and next_state.pending_tool_name in _SIDE_EFFECT_TOOLS:
            raise GuardrailViolationError("cannot end a session while a side effect requires reconciliation")

        if next_state.current_step == "RECONCILIATION_REQUIRED":
            if action.action_type is not ActionType.HANDOFF:
                raise GuardrailViolationError("reconciliation requires a handoff action")
            if next_state.pending_tool_name not in _SIDE_EFFECT_TOOLS:
                raise GuardrailViolationError("reconciliation requires a pending side effect")

        if action.action_type is ActionType.CALL_TOOL:
            assert action.tool_call is not None
            if state.tool_call_count >= self.policy.max_tool_calls_per_session:
                raise GuardrailViolationError("session tool-call limit was reached")
            if next_state.current_workflow is None or action.tool_call.tool_name not in _WORKFLOW_TOOLS.get(
                next_state.current_workflow, set()
            ):
                raise GuardrailViolationError("tool is not allowed for the active workflow")
            updates["tool_call_count"] = state.tool_call_count + 1
            next_state = state.apply(updates)
            if next_state.pending_tool_call_id != action.tool_call.call_id:
                raise GuardrailViolationError("tool call is not registered as pending")
            if next_state.pending_tool_name is not action.tool_call.tool_name:
                raise GuardrailViolationError("pending tool name does not match the action")
            if (
                action.tool_call.tool_name is ToolName.CREATE_BOOKING
                and next_state.confirmation is not ConfirmationStatus.CONFIRMED
            ):
                raise GuardrailViolationError("create_booking requires explicit confirmed state")
            if action.tool_call.tool_name is ToolName.CREATE_BOOKING:
                booking = next_state.collected_data.get("booking", {})
                if not isinstance(booking, dict):
                    raise GuardrailViolationError("create_booking requires booking state")
                locations = (booking.get("pickup"), booking.get("destination"))
                if any(
                    not isinstance(location, dict)
                    or not location.get("place_id")
                    or not location.get("display_name")
                    for location in locations
                ):
                    raise GuardrailViolationError("create_booking requires resolved concrete locations")
                pickup, destination = locations
                assert isinstance(pickup, dict)
                assert isinstance(destination, dict)
                if pickup.get("place_id") == destination.get("place_id"):
                    raise GuardrailViolationError("create_booking requires different pickup and destination")
                expected_params = {
                    "pickup_place_id": pickup.get("place_id"),
                    "destination_place_id": destination.get("place_id"),
                    "phone_number": booking.get("phone_number"),
                    "vehicle_type": booking.get("vehicle_type"),
                    "fare_estimate_id": booking.get("fare_estimate_id"),
                }
                if booking.get("passenger_count") is not None:
                    expected_params["passenger_count"] = booking.get("passenger_count")
                if booking.get("selected_vehicle_option_id") is not None:
                    expected_params["vehicle_option_id"] = booking.get("selected_vehicle_option_id")
                if any(value in {None, ""} for value in expected_params.values()):
                    raise GuardrailViolationError("create_booking requires complete booking and fare data")
                if any(action.tool_call.params.get(key) != value for key, value in expected_params.items()):
                    raise GuardrailViolationError("create_booking params must match confirmed booking state")
                if not action.tool_call.params.get("idempotency_key"):
                    raise GuardrailViolationError("create_booking requires an idempotency key")
            if action.tool_call.tool_name is ToolName.CANCEL_BOOKING:
                if next_state.confirmation is not ConfirmationStatus.CONFIRMED:
                    raise GuardrailViolationError("cancel_booking requires explicit confirmed state")
                booking = next_state.collected_data.get("booking", {})
                if not isinstance(booking, dict) or not booking.get("booking_id"):
                    raise GuardrailViolationError("cancel_booking requires a completed booking")
                if action.tool_call.params.get("booking_id") != booking.get("booking_id"):
                    raise GuardrailViolationError("cancel_booking params must match booking state")
                if not action.tool_call.params.get("idempotency_key"):
                    raise GuardrailViolationError("cancel_booking requires an idempotency key")
            try:
                validated_params = (
                    _TOOL_PARAM_MODELS[action.tool_call.tool_name]
                    .model_validate(action.tool_call.params)
                    .model_dump(exclude_none=True)
                )
            except ValidationError as exc:
                raise GuardrailViolationError("tool call contains invalid params") from exc
            if set(validated_params) != set(action.tool_call.params):
                raise GuardrailViolationError("tool call contains unexpected params")

        safe_tool_call = action.tool_call
        if safe_tool_call is not None and safe_tool_call.timeout_seconds is None:
            safe_tool_call = safe_tool_call.model_copy(
                update={"timeout_seconds": self.policy.tool_deadline_seconds(safe_tool_call.tool_name)}
            )
        return action.model_copy(
            update={
                "state_updates": updates,
                "reason": redact_pii(action.reason),
                "tool_call": safe_tool_call,
            },
            deep=True,
        )

    @staticmethod
    def safe_handoff(reason: str) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message=("Tôi chưa thể tiếp tục xử lý tự động. Tôi sẽ chuyển bạn tới tổng đài viên."),
            state_updates={
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "HANDOFF_REQUIRED",
                **clear_pending_tool_updates(),
            },
            reason=redact_pii(reason),
        )

    @staticmethod
    def safe_reconciliation_handoff(reason: str) -> AgentAction:
        return AgentAction(
            action_type=ActionType.HANDOFF,
            message=("Tôi cần kiểm tra trạng thái yêu cầu đang xử lý và sẽ chuyển bạn tới tổng đài viên."),
            state_updates={
                "current_workflow": WorkflowType.HUMAN_HANDOFF,
                "current_step": "RECONCILIATION_REQUIRED",
            },
            reason=redact_pii(reason),
        )


def redact_pii(value: str | None) -> str | None:
    if value is None:
        return None
    without_phone = _PHONE_PATTERN.sub("[REDACTED_PHONE]", value)
    return _BOOKING_ID_PATTERN.sub(r"\1[REDACTED_BOOKING_ID]", without_phone)


def redact_pii_data(value):
    """Redact PII recursively before data crosses a diagnostic/handoff boundary."""
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = str(key).casefold()
            if normalized_key in {"phone", "phone_number"} and item:
                redacted[key] = "[REDACTED_PHONE]"
            elif normalized_key in {"booking_id", "found_booking_id"} and item:
                redacted[key] = "[REDACTED_BOOKING_ID]"
            else:
                redacted[key] = redact_pii_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_pii_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_pii_data(item) for item in value)
    return value
