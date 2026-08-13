from collections.abc import Iterable

from src.agents.state import (
    AssistantDeliveryEvent,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)


class HistoryError(ValueError):
    pass


class DuplicateHistoryMessageError(HistoryError):
    pass


class DeliveryEventMismatchError(HistoryError):
    pass


class InvalidDeliveryTransitionError(HistoryError):
    pass


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
        message.turn_id
        for message in result
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT
    }
    for message in messages:
        if message.message_id in existing_ids:
            raise DuplicateHistoryMessageError(message.message_id)
        if (
            message.message_type is ConversationMessageType.USER_TRANSCRIPT
            and message.turn_id in user_turns
        ):
            raise DuplicateHistoryMessageError(
                f"user transcript already exists for turn {message.turn_id}"
            )
        result.append(message.model_copy(deep=True))
        existing_ids.add(message.message_id)
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT:
            user_turns.add(message.turn_id)
    return result[-max_messages:]


def acknowledge_assistant_delivery(
    history: list[ConversationMessage],
    event: AssistantDeliveryEvent,
    *,
    session_id: str,
) -> list[ConversationMessage]:
    if event.session_id != session_id:
        raise DeliveryEventMismatchError("delivery event belongs to another session")

    result = [message.model_copy(deep=True) for message in history]
    matches = [
        (index, message)
        for index, message in enumerate(result)
        if message.message_id == event.message_id
    ]
    if len(matches) != 1:
        raise DeliveryEventMismatchError("assistant message was not found")

    index, message = matches[0]
    if message.turn_id != event.turn_id:
        raise DeliveryEventMismatchError("delivery event turn_id does not match")
    if message.message_type is not ConversationMessageType.ASSISTANT_SPEECH:
        raise DeliveryEventMismatchError("delivery event target is not assistant speech")
    if message.delivery_status is not DeliveryStatus.PENDING:
        raise InvalidDeliveryTransitionError(
            "only pending assistant speech can receive delivery acknowledgement"
        )

    spoken_content = event.spoken_content
    if event.status is DeliveryStatus.DELIVERED:
        if spoken_content is not None and spoken_content != message.content:
            raise DeliveryEventMismatchError(
                "delivered spoken content must match the assistant message"
            )
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
