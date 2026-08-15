from typing import Protocol

from src.agents.context import ConversationContext
from src.agents.understanding.rewrite_models import RewriteDecision, RewriteResult


class RewriteProviderError(RuntimeError):
    pass


class RewriteTimeoutError(RewriteProviderError):
    pass


class InvalidRewriteOutputError(RewriteProviderError):
    pass


class UnsafeRewriteOutputError(RewriteProviderError):
    pass


class ContextualMessageRewriter(Protocol):
    async def rewrite(
        self,
        original_text: str,
        context: ConversationContext,
        decision: RewriteDecision,
    ) -> RewriteResult: ...
