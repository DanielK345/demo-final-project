from pydantic import ValidationError

from src.agents.capabilities.common import policy_error
from src.agents.contracts.schemas import ActionType, AgentAction, ToolName, ToolResult, WorkflowType
from src.agents.core.registry import ContinueToolLoop, RegisteredTool, ToolRegistry
from src.agents.core.session import TurnSession
from src.agents.core.tools import definition
from src.agents.tools.builders import LookupTripTool
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import clear_pending_tool_updates, parse_tool_result, pending_tool_updates
from src.agents.tools.schemas import LookupTripResult


def register_trip_lookup(registry: ToolRegistry) -> None:
    builder = LookupTripTool()

    def lookup(session: TurnSession, arguments: dict):
        booking_id = arguments.get("booking_id")
        phone_number = arguments.get("phone_number")
        try:
            call_id = build_call_id(
                session_id=session.state.session_id,
                workflow=WorkflowType.TRIP_LOOKUP,
                tool_name=ToolName.LOOKUP_TRIP,
                operation="trip",
                sequence=session.state.state_version + 1,
            )
            call = builder.build_call(call_id, booking_id=booking_id, phone_number=phone_number)
        except (ValidationError, ValueError):
            return policy_error("Cần mã chuyến hoặc số điện thoại hợp lệ để tra cứu.")
        session.trip.booking_id = booking_id
        session.trip.phone_number = phone_number
        session.persist("trip")
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=call,
            state_updates={
                **session.updates,
                "current_workflow": WorkflowType.TRIP_LOOKUP,
                **pending_tool_updates(call, waiting_step="WAITING_FOR_TRIP_RESULT"),
            },
            reason="Backend owns trip lookup; agent emitted a validated tool call.",
        )

    def select(session: TurnSession, arguments: dict):
        index = arguments.get("index")
        if not isinstance(index, int) or not 1 <= index <= len(session.trip.candidates):
            return policy_error("Lựa chọn chuyến không hợp lệ.")
        match = session.trip.candidates[index - 1]
        session.trip.selected_booking_id = match.booking_id
        session.trip.status = match.status
        session.trip.eta_minutes = match.eta_minutes
        session.trip.candidates = []
        session.persist("trip")
        return ContinueToolLoop({"trip_selected": match.model_dump(mode="json")})

    def reduce(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, LookupTripResult)
        session.updates.update(clear_pending_tool_updates())
        session.updates.update(current_step=None, retry_count=0)
        session.trip.completed_call_id = result.call_id
        if not payload.found:
            session.trip.candidates = []
            session.persist("trip")
            return ContinueToolLoop({"trip_lookup_result": {"found": False}})
        if payload.trips:
            session.trip.candidates = payload.trips
            session.persist("trip")
            return ContinueToolLoop({"trip_lookup_result": payload.model_dump(mode="json")})
        session.trip.selected_booking_id = payload.booking_id
        session.trip.status = payload.status
        session.trip.eta_minutes = payload.eta_minutes
        session.persist("trip")
        return ContinueToolLoop({"trip_lookup_result": payload.model_dump(mode="json")})

    registry.register(RegisteredTool(definition("lookup_trip"), lookup))
    registry.register(RegisteredTool(definition("select_trip"), select, lambda session: bool(session.trip.candidates)))
    registry.register_reducer(ToolName.LOOKUP_TRIP, reduce)
