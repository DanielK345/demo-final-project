"""Compatibility exports for callers that imported history helpers from src.agents."""

from src.agents.core.history import (
    DeliveryEventMismatchError,
    DuplicateHistoryMessageError,
    HistoryError,
    HistorySessionMismatchError,
    InvalidDeliveryTransitionError,
    acknowledge_assistant_delivery,
    append_history_messages,
    build_message_id,
    record_turn_history,
)

__all__ = [
    "DeliveryEventMismatchError",
    "DuplicateHistoryMessageError",
    "HistoryError",
    "HistorySessionMismatchError",
    "InvalidDeliveryTransitionError",
    "acknowledge_assistant_delivery",
    "append_history_messages",
    "build_message_id",
    "record_turn_history",
]
