from src.agents.contracts.schemas import ActionType, AgentAction
from src.agents.core.handoff import HandoffReason, classify_handoff, deterministic_handoff_action
from src.agents.core.registry import ContinueToolLoop, RegisteredTool, ToolRegistry
from src.agents.core.session import TurnSession
from src.agents.core.tools import definition


def respond(session: TurnSession, arguments: dict) -> AgentAction:
    message = str(arguments.get("message") or "").strip()
    if not message:
        return handoff(session, {"reason": "Conversation model returned an empty response"})
    if "knowledge_result" in session.event:
        session.faq.answer = message
        session.persist("faq")
        session.updates.update(current_workflow=None, current_step=None)
    if "trip_selected" in session.event or (
        "trip_lookup_result" in session.event and not session.trip.candidates
    ):
        session.updates.update(current_workflow=None, current_step=None)
    return AgentAction(
        action_type=ActionType.ASK_USER if arguments.get("expects_response") is True else ActionType.RESPOND,
        message=message,
        state_updates=session.updates,
        reason="The model produced a typed conversational response.",
    )


def handoff(session: TurnSession, arguments: dict) -> AgentAction:
    reason = str(arguments.get("reason") or "Model requested handoff").strip()
    requested_code = arguments.get("reason_code")
    try:
        reason_code = HandoffReason(str(requested_code)) if requested_code else None
    except ValueError:
        reason_code = None
    transcript = str(session.event.get("user_transcript") or "")
    reason_code = reason_code or classify_handoff(transcript) or classify_handoff(reason)
    return deterministic_handoff_action(
        session.state,
        reason_code=reason_code or HandoffReason.UNABLE_TO_CONTINUE,
        reason=reason,
        state_updates=session.updates,
    )


def register_common(registry: ToolRegistry) -> None:
    registry.register(RegisteredTool(definition("respond"), respond))
    registry.register(RegisteredTool(definition("handoff"), handoff))


def policy_error(message: str) -> ContinueToolLoop:
    return ContinueToolLoop({"policy_error": message})
