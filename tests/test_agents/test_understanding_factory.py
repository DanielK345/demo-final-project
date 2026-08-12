import pytest

from src.agents.understanding.factory import build_understanding_service
from src.agents.understanding.rules import RuleBasedUnderstanding
from src.agents.understanding.service import ResilientUnderstandingService
from src.config import Settings


def test_factory_uses_rules_when_agent_llm_is_disabled():
    service = build_understanding_service(
        Settings(agent_llm_enabled=False, openai_api_key="")
    )

    assert isinstance(service, RuleBasedUnderstanding)


def test_factory_requires_key_when_agent_llm_is_enabled():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_understanding_service(
            Settings(agent_llm_enabled=True, openai_api_key="")
        )


def test_factory_builds_resilient_openai_service_when_enabled():
    service = build_understanding_service(
        Settings(
            agent_llm_enabled=True,
            openai_api_key="test-key",
            agent_llm_model="test-model",
        )
    )

    assert isinstance(service, ResilientUnderstandingService)
    assert service.primary.model == "test-model"
