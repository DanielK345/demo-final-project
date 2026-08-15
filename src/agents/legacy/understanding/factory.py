from src.agents.legacy.understanding.base import LanguageUnderstandingPort
from src.agents.legacy.understanding.openai import OpenAIUnderstandingAdapter
from src.agents.legacy.understanding.rules import RuleBasedUnderstanding
from src.agents.legacy.understanding.service import ResilientUnderstandingService
from src.config import Settings, get_settings


def build_understanding_service(
    settings: Settings | None = None,
) -> LanguageUnderstandingPort:
    config = settings or get_settings()
    fallback = RuleBasedUnderstanding()
    if not config.agent_llm_enabled:
        return fallback
    if not config.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is required when AGENT_LLM_ENABLED is true"
        )
    primary = OpenAIUnderstandingAdapter(
        api_key=config.openai_api_key,
        model=config.agent_llm_model,
        timeout_seconds=config.agent_llm_timeout_seconds,
        reasoning_effort=config.agent_llm_reasoning_effort,
        base_url=config.agent_llm_base_url,
    )
    return ResilientUnderstandingService(primary=primary, fallback=fallback)
