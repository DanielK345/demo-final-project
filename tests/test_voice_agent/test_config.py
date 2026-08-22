import pytest
from pydantic import ValidationError

from src.voice_agent.config import LiveKitVoiceSettings


def settings(**overrides: object) -> LiveKitVoiceSettings:
    return LiveKitVoiceSettings(_env_file=None, **overrides)


def test_livekit_configuration_fails_closed_when_required_values_are_missing() -> None:
    config = settings()

    assert config.configuration_errors() == [
        "LIVEKIT_URL_REQUIRED",
        "LIVEKIT_API_KEY_REQUIRED",
        "LIVEKIT_API_SECRET_REQUIRED",
        "LIVEKIT_STT_MODEL_REQUIRED",
        "LIVEKIT_LLM_MODEL_REQUIRED",
        "LIVEKIT_TTS_MODEL_REQUIRED",
        "LIVEKIT_TTS_VOICE_REQUIRED",
    ]
    with pytest.raises(ValueError, match="LIVEKIT_URL_REQUIRED"):
        config.require_configured()


def test_livekit_accepts_complete_native_pipeline_configuration() -> None:
    config = settings(
        livekit_url="wss://alosm.example.livekit.cloud",
        livekit_api_key="api-key",
        livekit_api_secret="api-secret",
        livekit_stt_model="provider/stt-model",
        livekit_llm_model="provider/llm-model",
        livekit_tts_model="provider/tts-model",
        livekit_tts_voice="vi-voice",
    )

    assert config.configuration_errors() == []
    assert config.livekit_turn_detection == "vad"
    assert config.livekit_llm_provider == "livekit"
    assert config.livekit_tts_provider == "livekit"
    assert config.livekit_interruption_mode == "vad"
    assert config.livekit_endpointing_mode == "fixed"
    assert config.livekit_endpointing_min_delay_seconds == 2.0
    assert config.livekit_endpointing_max_delay_seconds == 3.0
    assert config.livekit_interruption_min_duration_seconds == 0.5
    assert config.livekit_transcription_timeout_seconds == 5.0
    assert config.livekit_stt_language == "vi"
    assert config.livekit_tts_language == "vi"
    assert config.livekit_record_audio is False
    assert config.livekit_record_transcript is False
    assert config.livekit_debug_event_log is False
    assert config.livekit_debug_transcripts is False
    assert config.livekit_delete_room_on_close is False
    assert str(config.livekit_debug_log_dir) == "logs/livekit"
    config.require_configured()


def test_livekit_url_must_use_websocket_scheme() -> None:
    config = settings(
        livekit_url="https://alosm.example.livekit.cloud",
        livekit_api_key="api-key",
        livekit_api_secret="api-secret",
        livekit_stt_model="provider/stt",
        livekit_llm_model="provider/llm",
        livekit_tts_model="provider/tts",
        livekit_tts_voice="voice",
    )

    assert config.configuration_errors() == ["LIVEKIT_URL_MUST_USE_WS"]


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("livekit_stt_model", "chirp_2", "LIVEKIT_STT_MODEL_MUST_USE_PROVIDER_MODEL"),
        ("livekit_llm_model", "gpt-4.1-mini", "LIVEKIT_LLM_MODEL_MUST_USE_PROVIDER_MODEL"),
        ("livekit_tts_model", "gpt-4o-mini-tts", "LIVEKIT_TTS_MODEL_MUST_USE_PROVIDER_MODEL"),
    ],
)
def test_livekit_inference_models_require_provider_prefix(
    field: str,
    value: str,
    expected_error: str,
) -> None:
    values = {
        "livekit_stt_model": "deepgram/nova-3",
        "livekit_llm_model": "openai/gpt-4.1-mini",
        "livekit_tts_model": "cartesia/sonic-3",
    }
    values[field] = value
    config = settings(**values)

    assert expected_error in config.configuration_errors()


def test_livekit_stt_auto_model_is_supported() -> None:
    config = settings(livekit_stt_model="auto")

    assert "LIVEKIT_STT_MODEL_MUST_USE_PROVIDER_MODEL" not in config.configuration_errors()


def test_semantic_turn_detection_cannot_be_selected_by_configuration() -> None:
    with pytest.raises(ValidationError):
        settings(livekit_turn_detection="semantic")


def test_endpointing_max_delay_cannot_be_lower_than_minimum() -> None:
    config = settings(
        livekit_endpointing_min_delay_seconds=1.5,
        livekit_endpointing_max_delay_seconds=1.0,
    )

    assert "LIVEKIT_ENDPOINTING_MAX_MUST_NOT_BE_LOWER_THAN_MIN" in config.configuration_errors()


def test_debug_transcripts_require_explicit_event_log_opt_in() -> None:
    config = settings(livekit_debug_transcripts=True)

    assert "LIVEKIT_DEBUG_TRANSCRIPTS_REQUIRES_EVENT_LOG" in config.configuration_errors()


def test_openai_llm_provider_requires_its_own_api_key() -> None:
    config = settings(livekit_llm_provider="openai", openai_api_key="")

    assert "OPENAI_API_KEY_REQUIRED_FOR_OPENAI_PROVIDER" in config.configuration_errors()


def test_openai_tts_provider_requires_its_own_api_key() -> None:
    config = settings(livekit_tts_provider="openai", openai_api_key="")

    assert "OPENAI_API_KEY_REQUIRED_FOR_OPENAI_PROVIDER" in config.configuration_errors()


def test_standalone_google_stt_benchmark_does_not_require_llm_or_tts() -> None:
    config = settings(
        livekit_stt_provider="google",
        livekit_stt_model="chirp_2",
        livekit_stt_language="vi-VN",
        google_cloud_project="project-id",
        google_stt_location="asia-southeast1",
    )

    assert config.stt_configuration_errors() == []
    config.require_stt_configured()
