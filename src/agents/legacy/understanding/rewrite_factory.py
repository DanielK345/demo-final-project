from src.agents.legacy.understanding.rewrite_base import ContextualMessageRewriter
from src.agents.legacy.understanding.rewrite_openai import OpenAIContextualRewriteAdapter
from src.agents.legacy.understanding.rewrite_service import (
    PassthroughContextualRewriter,
    ResilientContextualRewriteService,
)
from src.config import Settings, get_settings


def build_contextual_rewriter(
    settings: Settings | None = None,
) -> ContextualMessageRewriter:
    config = settings or get_settings()
    if not config.agent_rewrite_enabled:
        return PassthroughContextualRewriter()
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when AGENT_REWRITE_ENABLED is true")
    primary = OpenAIContextualRewriteAdapter(
        api_key=config.openai_api_key,
        model=config.agent_rewrite_model,
        timeout_seconds=config.agent_rewrite_timeout_seconds,
        reasoning_effort=config.agent_rewrite_reasoning_effort,
        base_url=config.agent_rewrite_base_url,
    )
    return ResilientContextualRewriteService(primary=primary)
