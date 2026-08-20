from src.backend.config import Settings
from src.backend.services.transcript_rewriter import transcript_rewriter_disabled_reason


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "voice_transcript_rewrite_enabled": True,
        "voice_transcript_rewrite_base_url": "https://api.openai.com/v1",
        "openai_api_key": "test-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_rewriter_diagnostic_distinguishes_disabled_config() -> None:
    assert (
        transcript_rewriter_disabled_reason(
            _settings(voice_transcript_rewrite_enabled=False),
        )
        == "config_disabled"
    )


def test_rewriter_diagnostic_distinguishes_missing_matching_key() -> None:
    assert transcript_rewriter_disabled_reason(_settings(openai_api_key="")) == "missing_api_key"


def test_rewriter_diagnostic_reports_ready_configuration() -> None:
    assert transcript_rewriter_disabled_reason(_settings()) is None
