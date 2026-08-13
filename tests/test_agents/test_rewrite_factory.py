import pytest

from src.agents.understanding.rewrite_factory import build_contextual_rewriter
from src.agents.understanding.rewrite_service import (
    PassthroughContextualRewriter,
    ResilientContextualRewriteService,
)
from src.config import Settings


def test_rewrite_factory_uses_passthrough_when_disabled():
    rewriter = build_contextual_rewriter(Settings(agent_rewrite_enabled=False, openai_api_key=""))

    assert isinstance(rewriter, PassthroughContextualRewriter)


def test_rewrite_factory_requires_key_when_enabled():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_contextual_rewriter(Settings(agent_rewrite_enabled=True, openai_api_key=""))


def test_rewrite_factory_builds_resilient_openai_service():
    rewriter = build_contextual_rewriter(
        Settings(
            agent_rewrite_enabled=True,
            openai_api_key="test-key",
            agent_rewrite_model="rewrite-model",
        )
    )

    assert isinstance(rewriter, ResilientContextualRewriteService)
    assert rewriter.primary.model == "rewrite-model"
