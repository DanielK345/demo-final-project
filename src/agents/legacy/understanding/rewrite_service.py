from src.agents.legacy.context_models import ConversationContext
from src.agents.legacy.understanding.rewrite_base import (
    ContextualMessageRewriter,
    InvalidRewriteOutputError,
    RewriteProviderError,
    RewriteTimeoutError,
    UnsafeRewriteOutputError,
)
from src.agents.legacy.understanding.rewrite_models import RewriteDecision, RewriteResult
from src.agents.legacy.understanding.rewrite_safety import (
    contains_sensitive_identity,
    validate_rewrite_result,
)


class PassthroughContextualRewriter:
    def __init__(self, *, ambiguity: str = "rewrite_disabled") -> None:
        self.ambiguity = ambiguity

    async def rewrite(
        self,
        original_text: str,
        context: ConversationContext,
        decision: RewriteDecision,
    ) -> RewriteResult:
        del context, decision
        return RewriteResult.unchanged(original_text, ambiguity=self.ambiguity)


class ResilientContextualRewriteService:
    def __init__(self, primary: ContextualMessageRewriter) -> None:
        self.primary = primary

    async def rewrite(
        self,
        original_text: str,
        context: ConversationContext,
        decision: RewriteDecision,
    ) -> RewriteResult:
        if not decision.should_rewrite:
            return RewriteResult.unchanged(original_text)
        if not original_text.strip():
            return RewriteResult.unchanged(original_text, ambiguity="empty_input")
        if contains_sensitive_identity(original_text):
            return RewriteResult.unchanged(original_text, ambiguity="sensitive_input")

        try:
            result = await self.primary.rewrite(original_text, context, decision)
            return validate_rewrite_result(
                result,
                original_text=original_text,
                context=context,
                decision=decision,
            )
        except RewriteTimeoutError:
            ambiguity = "rewrite_timeout"
        except InvalidRewriteOutputError:
            ambiguity = "invalid_rewrite_output"
        except UnsafeRewriteOutputError:
            ambiguity = "unsafe_rewrite_output"
        except RewriteProviderError:
            ambiguity = "rewrite_provider_error"
        return RewriteResult.unchanged(original_text, ambiguity=ambiguity)
