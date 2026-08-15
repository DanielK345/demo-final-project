from collections.abc import Iterable

from src.agents.contracts.schemas import ActionType, AgentAction, AgentInput
from src.agents.contracts.state import (
    AgentState,
    AssistantDeliveryEvent,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)
from src.agents.core.guardrails import redact_pii


class HistoryError(ValueError):
    pass


class DuplicateHistoryMessageError(HistoryError):
    pass


class DeliveryEventMismatchError(HistoryError):
    pass


class InvalidDeliveryTransitionError(HistoryError):
    pass


class HistorySessionMismatchError(HistoryError):
    pass


_SPOKEN_ACTIONS = {
    ActionType.ASK_USER,
    ActionType.RESPOND,
    ActionType.HANDOFF,
    ActionType.END_SESSION,
}


def build_message_id(
    turn_id: str,
    role: ConversationRole,
    *,
    sequence: int | None = None,
) -> str:
    normalized_turn_id = turn_id.strip()
    if not normalized_turn_id:
        raise ValueError("turn_id cannot be blank")
    if role is ConversationRole.TOOL:
        if sequence is None or sequence < 1:
            raise ValueError("tool history messages require a positive sequence")
        return f"{normalized_turn_id}:tool-summary:{sequence}"
    if sequence is not None:
        raise ValueError("sequence is only valid for tool history messages")
    return f"{normalized_turn_id}:{role.value.lower()}"


def append_history_messages(
    history: list[ConversationMessage],
    messages: Iterable[ConversationMessage],
    *,
    max_messages: int,
) -> list[ConversationMessage]:
    if max_messages < 1:
        raise ValueError("max_messages must be positive")

    result = [message.model_copy(deep=True) for message in history]
    existing_ids = {message.message_id for message in result}
    user_turns = {
        message.turn_id for message in result if message.message_type is ConversationMessageType.USER_TRANSCRIPT
    }
    for message in messages:
        if message.message_id in existing_ids:
            raise DuplicateHistoryMessageError(message.message_id)
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT and message.turn_id in user_turns:
            raise DuplicateHistoryMessageError(f"user transcript already exists for turn {message.turn_id}")
        result.append(message.model_copy(deep=True))
        existing_ids.add(message.message_id)
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT:
            user_turns.add(message.turn_id)
    return _prune_complete_turns(result, max_messages=max_messages)


def record_turn_history(
    agent_input: AgentInput,
    state: AgentState,
    action: AgentAction,
) -> AgentAction:
    """Return an action whose partial update atomically includes this turn's history."""
    if agent_input.session_id != state.session_id:
        raise HistorySessionMismatchError("agent input and history state must belong to the same session")
    messages: list[ConversationMessage] = []
    transcript = agent_input.transcript.strip()
    if transcript:
        messages.append(
            ConversationMessage(
                message_id=build_message_id(
                    agent_input.turn_id,
                    ConversationRole.USER,
                ),
                turn_id=agent_input.turn_id,
                role=ConversationRole.USER,
                message_type=ConversationMessageType.USER_TRANSCRIPT,
                content=_bounded_content(redact_pii(transcript) or transcript),
                delivery_status=DeliveryStatus.FINAL,
                stt_confidence=agent_input.stt_confidence,
            )
        )

    if agent_input.tool_result is not None:
        messages.append(
            ConversationMessage(
                message_id=build_message_id(
                    agent_input.turn_id,
                    ConversationRole.TOOL,
                    sequence=1,
                ),
                turn_id=agent_input.turn_id,
                role=ConversationRole.TOOL,
                message_type=ConversationMessageType.TOOL_SUMMARY,
                content=(f"{agent_input.tool_result.tool_name.value} returned {agent_input.tool_result.status.value}."),
                delivery_status=DeliveryStatus.FINAL,
            )
        )

    if action.action_type in _SPOKEN_ACTIONS and action.message:
        sanitized_message = redact_pii(action.message)
        assert sanitized_message is not None
        messages.append(
            ConversationMessage(
                message_id=build_message_id(
                    agent_input.turn_id,
                    ConversationRole.ASSISTANT,
                ),
                turn_id=agent_input.turn_id,
                role=ConversationRole.ASSISTANT,
                message_type=ConversationMessageType.ASSISTANT_SPEECH,
                content=_bounded_content(sanitized_message),
                delivery_status=DeliveryStatus.PENDING,
            )
        )

    if not messages:
        return action.model_copy(deep=True)

    history = append_history_messages(
        state.conversation_history,
        messages,
        max_messages=state.max_history_messages,
    )
    updates = {**action.state_updates, "conversation_history": history}
    state.apply(updates)
    return action.model_copy(update={"state_updates": updates}, deep=True)


def _prune_complete_turns(
    history: list[ConversationMessage],
    *,
    max_messages: int,
) -> list[ConversationMessage]:
    result = history
    while len(result) > max_messages:
        oldest_turn_id = result[0].turn_id
        without_oldest_turn = [message for message in result if message.turn_id != oldest_turn_id]
        if not without_oldest_turn:
            return result[-max_messages:]
        result = without_oldest_turn
    return result


def _bounded_content(value: str, *, max_characters: int = 2000) -> str:
    if len(value) <= max_characters:
        return value
    return f"{value[: max_characters - 3].rstrip()}..."


def acknowledge_assistant_delivery(
    history: list[ConversationMessage],
    event: AssistantDeliveryEvent,
    *,
    session_id: str,
) -> list[ConversationMessage]:
    if event.session_id != session_id:
        raise DeliveryEventMismatchError("delivery event belongs to another session")

    result = [message.model_copy(deep=True) for message in history]
    matches = [(index, message) for index, message in enumerate(result) if message.message_id == event.message_id]
    if len(matches) != 1:
        raise DeliveryEventMismatchError("assistant message was not found")

    index, message = matches[0]
    if message.turn_id != event.turn_id:
        raise DeliveryEventMismatchError("delivery event turn_id does not match")
    if message.message_type is not ConversationMessageType.ASSISTANT_SPEECH:
        raise DeliveryEventMismatchError("delivery event target is not assistant speech")
    if message.delivery_status is not DeliveryStatus.PENDING:
        raise InvalidDeliveryTransitionError("only pending assistant speech can receive delivery acknowledgement")

    spoken_content = event.spoken_content
    if event.status is DeliveryStatus.DELIVERED:
        if spoken_content is not None and spoken_content != message.content:
            raise DeliveryEventMismatchError("delivered spoken content must match the assistant message")
        spoken_content = message.content
    values = message.model_dump()
    values.update(
        {
            "delivery_status": event.status,
            "spoken_content": spoken_content,
        }
    )
    result[index] = ConversationMessage.model_validate(values)
    return result
