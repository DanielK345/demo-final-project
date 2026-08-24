from scripts.ai_log_privacy import REDACTED, redact_secrets, redact_text


def test_redact_text_removes_provider_keys_and_bearer_tokens() -> None:
    text = "OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz Authorization: Bearer abcdefghijklmnopqrstuvwxyz"

    redacted = redact_text(text)

    assert "sk-or-v1-" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
    assert REDACTED in redacted


def test_redact_secrets_walks_nested_payload_without_mutating_input() -> None:
    source = {
        "tool_input": {"api_key": "very-sensitive-value", "query": "đặt xe"},
        "items": [{"OPENAI_API_KEY": "another-secret-value"}],
        "max_tokens": 100,
    }

    result = redact_secrets(source)

    assert result["tool_input"]["api_key"] == REDACTED
    assert result["items"][0]["OPENAI_API_KEY"] == REDACTED
    assert result["max_tokens"] == 100
    assert source["tool_input"]["api_key"] == "very-sensitive-value"


def test_redaction_keeps_non_secret_token_language() -> None:
    source = {"token_budget": 500, "prompt": "Count output tokens carefully"}

    assert redact_secrets(source) == source
