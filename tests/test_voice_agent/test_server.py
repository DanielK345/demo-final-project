import asyncio

import pytest
from livekit.agents import AgentSession

from src.voice_agent.config import LiveKitVoiceSettings
from src.voice_agent.server import (
    build_agent_session,
    prepare_process,
    request_initial_greeting,
    restore_session_data,
)
from src.voice_agent.session_data import AloSMSessionData


def _settings(**overrides: object) -> LiveKitVoiceSettings:
    values: dict[str, object] = {
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
    assert session.options.interruption["min_words"] == 0
    assert session.options.transcription_timeout == 5.0


@pytest.mark.asyncio
async def test_adaptive_interruption_requires_explicit_configuration() -> None:
    session = build_agent_session(_settings(livekit_interruption_mode="adaptive"))

    assert session.options.interruption["mode"] == "adaptive"


@pytest.mark.asyncio
async def test_build_agent_session_can_use_openai_plugin_without_changing_voice_pipeline() -> None:
    session = build_agent_session(
        _settings(
            livekit_llm_provider="openai",
            livekit_llm_model="gpt-4.1-mini",
            openai_api_key="test-openai-key",
        )
    )

    assert isinstance(session, AgentSession)
    assert session.llm.model == "gpt-4.1-mini"


@pytest.mark.asyncio
async def test_build_agent_session_can_use_openai_tts_plugin() -> None:
    session = build_agent_session(
        _settings(
            livekit_tts_provider="openai",
            livekit_tts_model="gpt-4o-mini-tts",
            livekit_tts_voice="ash",
            openai_api_key="test-openai-key",
        )
    )

    assert isinstance(session, AgentSession)
    assert session.tts.model == "gpt-4o-mini-tts"


def test_build_agent_session_fails_closed_before_worker_start() -> None:
    with pytest.raises(ValueError, match="LIVEKIT_STT_MODEL_REQUIRED"):
        build_agent_session(_settings(livekit_stt_model=""))


def test_livekit_process_setup_prewarms_native_models_and_state_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        userdata: dict[str, object] = {}

    warmed_vad = object()
    warmed_stt = object()
    monkeypatch.setattr("src.voice_agent.server.inference.VAD", lambda **_: warmed_vad)
    monkeypatch.setattr("src.voice_agent.server.build_stt", lambda _: warmed_stt)

    prepare_process(Process())  # type: ignore[arg-type]

    assert Process.userdata["alosm_process_store_ready"] is True
    assert Process.userdata["alosm_voice_state_store"] is not None
    assert Process.userdata["alosm_prewarmed_vad"] is warmed_vad
    assert Process.userdata["alosm_prewarmed_stt"] is warmed_stt
    assert Process.userdata["alosm_prewarmed_knowledge"] is not None
    assert Process.userdata["alosm_prewarmed_pricing"] is not None


def test_new_call_greeting_uses_native_say_without_llm() -> None:
    class Session:
        userdata = AloSMSessionData(
            app_session_id="session",
            call_id="call",
            user_id="user",
            participant_identity="participant",
        )

        def __init__(self) -> None:
            self.said: list[tuple[str, bool]] = []
            self.generated = False

        def say(self, text: str, *, allow_interruptions: bool) -> None:
            self.said.append((text, allow_interruptions))

        def generate_reply(self, **_: object) -> None:
            self.generated = True

    session = Session()

    request_initial_greeting(session, recovered=False)  # type: ignore[arg-type]

    assert session.said == [
        (
            "Chào bạn, tôi là tổng đài viên AloSM. "
            "Bạn vui lòng cho biết yêu cầu đặt xe của mình nhé?",
            True,
        )
    ]
    assert session.generated is False


@pytest.mark.asyncio
async def test_new_session_restore_does_not_write_empty_state_on_startup() -> None:
    class EmptyStore:
        async def restore(self, userdata) -> bool:  # type: ignore[no-untyped-def]
            return False

        async def save(self, userdata) -> None:  # type: ignore[no-untyped-def]
            raise AssertionError("empty state must not add a second startup round-trip")

    userdata = AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
    )

    recovered = await restore_session_data(userdata, EmptyStore(), timeout_seconds=1)  # type: ignore[arg-type]

    assert recovered is False
    assert userdata.persistence_enabled is True


@pytest.mark.asyncio
async def test_state_restore_timeout_falls_back_without_blocking_voice_session() -> None:
    class HangingStore:
        async def restore(self, userdata) -> bool:  # type: ignore[no-untyped-def]
            await asyncio.Event().wait()
            return False

        async def save(self, userdata) -> None:  # type: ignore[no-untyped-def]
            raise AssertionError("save must not run after restore timeout")

    userdata = AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
    )

    recovered = await restore_session_data(
        userdata,
        HangingStore(),  # type: ignore[arg-type]
        timeout_seconds=0.001,
    )

    assert recovered is False
    assert userdata.persistence_enabled is False
    assert userdata.last_failure is not None
    assert userdata.last_failure.code == "SESSION_RECOVERY_FAILED"
