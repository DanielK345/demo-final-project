import pytest
from livekit.agents import AgentSession

from src.voice_agent.config import LiveKitVoiceSettings
from src.voice_agent.server import build_agent_session


def _settings(**overrides: object) -> LiveKitVoiceSettings:
    values: dict[str, object] = {
        "voice_runtime": "livekit",
        "livekit_url": "wss://alosm.test.livekit.cloud",
        "livekit_api_key": "api-key",
        "livekit_api_secret": "test-api-secret-with-at-least-32-bytes",
        "livekit_stt_model": "deepgram/nova-3",
        "livekit_llm_model": "google/gemma-4-31b-it",
        "livekit_tts_model": "cartesia/sonic-3",
        "livekit_tts_voice": "test-voice",
    }
    values.update(overrides)
    return LiveKitVoiceSettings(_env_file=None, **values)


@pytest.mark.asyncio
async def test_build_agent_session_uses_livekit_native_pipeline() -> None:
    session = build_agent_session(_settings())

    assert isinstance(session, AgentSession)
    assert session.userdata.booking_draft.public_state()["confirmation_status"] == "not_requested"
    assert session.options.endpointing["mode"] == "fixed"
    assert session.options.endpointing["min_delay"] == 2.0
    assert session.options.endpointing["max_delay"] == 3.0
    assert session.options.interruption["mode"] == "vad"
    assert session.options.interruption["min_duration"] == 0.5
    assert session.options.interruption["min_words"] == 1
    assert session.options.preemptive_generation["enabled"] is False
    assert _settings().livekit_stt_final_fallback_enabled is True
    assert _settings().livekit_stt_final_fallback_seconds == 3.0


@pytest.mark.asyncio
async def test_adaptive_interruption_requires_explicit_configuration() -> None:
    session = build_agent_session(_settings(livekit_interruption_mode="adaptive"))

    assert session.options.interruption["mode"] == "adaptive"


def test_build_agent_session_fails_closed_before_worker_start() -> None:
    with pytest.raises(ValueError, match="LIVEKIT_STT_MODEL_REQUIRED"):
        build_agent_session(_settings(livekit_stt_model=""))
