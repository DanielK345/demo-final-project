"""Compatibility exports for the legacy contextual conversation builder."""

from src.agents.legacy.context import (
    ContextError,
    ContextSessionMismatchError,
    ConversationContextBuilder,
)
from src.agents.legacy.context_models import (
    BusinessContextField,
    CandidateField,
    ContextCandidate,
    ContextMessage,
    ContextSummary,
    ConversationContext,
)

__all__ = [
    "BusinessContextField",
    "CandidateField",
    "ContextCandidate",
    "ContextError",
    "ContextMessage",
    "ContextSessionMismatchError",
    "ContextSummary",
    "ConversationContext",
    "ConversationContextBuilder",
]
