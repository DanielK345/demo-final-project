from src.agents.contracts.schemas import ActionType, AgentAction, WorkflowType
from src.agents.core.registry import ContinueToolLoop, RegisteredTool, ToolRegistry
from src.agents.core.session import HandoffState, TurnSession
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
    history = session.state.conversation_history[-6:]
    summary = " | ".join(f"{item.role.value}: {item.content}" for item in history)
    context = HandoffState(
        reason=reason,
        source_workflow=(session.state.current_workflow.value if session.state.current_workflow else None),
        summary=summary or "No prior conversation summary.",
        pending_tool=(session.state.pending_tool_name.value if session.state.pending_tool_name else None),
    )
    collected = dict(session.updates.get("collected_data", session.state.collected_data))
    collected["handoff"] = context.model_dump(mode="json")
    return AgentAction(
        action_type=ActionType.HANDOFF,
        message="Tôi sẽ chuyển bạn tới tổng đài viên và gửi kèm nội dung đã trao đổi.",
        state_updates={
            **session.updates,
            "collected_data": collected,
            "current_workflow": WorkflowType.HUMAN_HANDOFF,
            "current_step": "HANDOFF_REQUIRED",
        },
        reason=reason,
    )


def register_common(registry: ToolRegistry) -> None:
    registry.register(RegisteredTool(definition("respond"), respond))
    registry.register(RegisteredTool(definition("handoff"), handoff))


def policy_error(message: str) -> ContinueToolLoop:
    return ContinueToolLoop({"policy_error": message})
