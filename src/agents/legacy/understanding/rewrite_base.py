from typing import Protocol

from src.agents.legacy.context_models import ConversationContext
from src.agents.legacy.understanding.rewrite_models import RewriteDecision, RewriteResult


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
