"""LiveKit AgentServer worker for the AloSM voice runtime."""

from __future__ import annotations

import asyncio
import json
import logging

from livekit.agents import AgentServer, AgentSession, JobContext, cli, inference
from livekit.agents.voice.events import ErrorEvent
from livekit.agents.voice.room_io import AudioInputOptions, RoomOptions

from src.backend.services.transcript_rewriter import (
    build_transcript_rewriter,
    transcript_rewriter_disabled_reason,
)
from src.config import Settings
from src.voice_agent.agent import AloSMAgent
from src.voice_agent.config import LiveKitVoiceSettings, get_livekit_voice_settings
from src.voice_agent.observability import LiveKitSessionObserver, SessionEventLog
from src.voice_agent.persistence import DatabaseVoiceStateStore, VoiceStateStore
from src.voice_agent.session_data import AloSMSessionData, FailureCode, FallbackAction
from src.voice_agent.state_sync import publish_booking_state, publish_transcript_rewrite
from src.voice_agent.stt_final_fallback import STTFinalFallback

logger = logging.getLogger(__name__)


def _build_stt(settings: LiveKitVoiceSettings, inference_credentials: dict):
    """Return the correct STT provider based on LIVEKIT_STT_PROVIDER env."""
    if settings.livekit_stt_provider == "zipformer":
        from src.voice_agent.custom_stt import ZipformerSTT  # noqa: PLC0415
        logger.info(
            "Using Zipformer STT url=%s", settings.zipformer_ws_url
        )
        return ZipformerSTT(
            url=settings.zipformer_ws_url,
            language=settings.livekit_stt_language,
        )
    return inference.STT(
        model=settings.livekit_stt_model,
        language=settings.livekit_stt_language,
        **inference_credentials,
    )


def build_agent_session(
    settings: LiveKitVoiceSettings,
    *,
    userdata: AloSMSessionData | None = None,
) -> AgentSession[AloSMSessionData]:
    """Build the native cascaded pipeline without legacy orchestration adapters."""

    settings.require_configured()
    userdata = userdata or AloSMSessionData(
        app_session_id="local-smoke-session",
        call_id="local-smoke-call",
        user_id="local-smoke-user",
        participant_identity="local-smoke-participant",
        recording_enabled=settings.livekit_record_audio,
        critical_confidence_threshold=settings.livekit_critical_confidence_threshold,
    )
    api_key = settings.livekit_api_key.get_secret_value()
    api_secret = settings.livekit_api_secret.get_secret_value()
    inference_credentials = {
        "api_key": api_key,
        "api_secret": api_secret,
    }
    return AgentSession(
        userdata=userdata,
        vad=inference.VAD(model="silero"),
        stt=_build_stt(settings, inference_credentials),
        llm=inference.LLM(
            model=settings.livekit_llm_model,
            **inference_credentials,
        ),
        tts=inference.TTS(
            model=settings.livekit_tts_model,
            voice=settings.livekit_tts_voice,
            language=settings.livekit_tts_language,
            **inference_credentials,
        ),
        turn_handling={
            "turn_detection": settings.livekit_turn_detection,
            "endpointing": {
                "mode": settings.livekit_endpointing_mode,
                "min_delay": settings.livekit_endpointing_min_delay_seconds,
                "max_delay": settings.livekit_endpointing_max_delay_seconds,
            },
            "interruption": {
                "enabled": True,
                "mode": settings.livekit_interruption_mode,
                "min_duration": settings.livekit_interruption_min_duration_seconds,
                "min_words": settings.livekit_interruption_min_words,
                "false_interruption_timeout": 2.0,
                "resume_false_interruption": True,
            },
            "preemptive_generation": {
                # Rewriting mutates the final ChatMessage. Starting the
                # conversation LLM from partial STT can race that mutation and
                # create duplicate replies for one interrupted utterance.
                "enabled": False,
                "preemptive_tts": False,
            },
        },
    )


def build_session_data(ctx: JobContext, settings: LiveKitVoiceSettings) -> AloSMSessionData:
    """Build privacy-safe business userdata from trusted dispatch metadata."""

    try:
        metadata = json.loads(ctx.job.metadata or "{}")
    except (json.JSONDecodeError, TypeError):
        metadata = {}
    participant = getattr(ctx.job, "participant", None)
    participant_identity = str(getattr(participant, "identity", "") or "unknown-participant")
    app_session_id = str(metadata.get("app_session_id") or ctx.job.id)
    return AloSMSessionData(
        app_session_id=app_session_id,
        call_id=str(ctx.job.id),
        # LiveKit identity is already an opaque server-generated account hash.
        user_id=participant_identity,
        participant_identity=participant_identity,
        consent_granted=True,
        recording_enabled=settings.livekit_record_audio,
        critical_confidence_threshold=settings.livekit_critical_confidence_threshold,
    )


async def restore_session_data(
    userdata: AloSMSessionData,
    state_store: VoiceStateStore,
) -> bool:
    """Restore a draft before AgentSession starts, with an explicit safe fallback."""

    try:
        recovered = await state_store.restore(userdata)
        if not recovered and userdata.persistence_enabled:
            await state_store.save(userdata)
        return recovered
    except Exception:
        logger.exception("failed to restore LiveKit voice state")
        userdata.persistence_enabled = False
        userdata.record_failure(
            "SESSION_RECOVERY_FAILED",
            "Không thể khôi phục phiên trước; cuộc gọi tiếp tục với trạng thái mới.",
            fallback_action="none",
        )
        return False


def _provider_failure(event: ErrorEvent) -> tuple[FailureCode, str, FallbackAction]:
    kind = f"{type(event.source).__name__} {type(event.error).__name__}".lower()
    if "stt" in kind:
        return "STT_UNAVAILABLE", "Nhận dạng giọng nói tạm thời lỗi.", "repeat_or_text"
    if "tts" in kind:
        return "TTS_UNAVAILABLE", "Phát giọng nói tạm thời lỗi; bạn có thể đọc tin nhắn.", "retry"
    return "LLM_UNAVAILABLE", "Tổng đài xử lý tạm thời lỗi.", "retry"


def register_provider_failure_sync(
    session: AgentSession[AloSMSessionData],
    state_store: VoiceStateStore,
) -> None:
    """Map native LiveKit provider errors to the public recovery contract."""

    async def persist_failure(event: ErrorEvent) -> None:
        code, message, fallback = _provider_failure(event)
        session.userdata.record_failure(code, message, fallback_action=fallback)
        try:
            await state_store.save(session.userdata)
        except Exception:
            logger.exception("failed to persist LiveKit provider failure")
        await publish_booking_state(session)

    @session.on("error")
    def on_error(event: ErrorEvent) -> None:
        asyncio.create_task(persist_failure(event))


_server_settings = get_livekit_voice_settings()
server = AgentServer(
    ws_url=_server_settings.livekit_url or None,
    api_key=_server_settings.livekit_api_key.get_secret_value() or None,
    api_secret=_server_settings.livekit_api_secret.get_secret_value() or None,
    num_idle_processes=_server_settings.livekit_num_idle_processes,
)


@server.rtc_session(agent_name=get_livekit_voice_settings().livekit_agent_name)
async def alosm_voice_session(ctx: JobContext) -> None:
    """Run one LiveKit AgentSession for one Room call."""

    settings = get_livekit_voice_settings()
    userdata = build_session_data(ctx, settings)
    state_store = DatabaseVoiceStateStore()
    # Read rewrite settings per job. LiveKit keeps idle worker processes warm,
    # so using the shared settings cache here could preserve a stale pre-fork
    # view of .env even though a new Room session has started.
    rewrite_settings = Settings()
    transcript_rewrite_disabled_reason = transcript_rewriter_disabled_reason(rewrite_settings)
    transcript_rewriter = build_transcript_rewriter(rewrite_settings)
    if transcript_rewrite_disabled_reason is not None:
        logger.warning(
            "LiveKit transcript rewrite unavailable reason=%s",
            transcript_rewrite_disabled_reason,
        )
    if transcript_rewriter is not None:
        ctx.add_shutdown_callback(transcript_rewriter.client.close)
    recovered = await restore_session_data(userdata, state_store)
    session = build_agent_session(settings, userdata=userdata)
    register_provider_failure_sync(session, state_store)
    stt_final_fallback: STTFinalFallback | None = None
    if settings.livekit_stt_final_fallback_enabled:
        stt_final_fallback = STTFinalFallback(
            session,
            delay_seconds=settings.livekit_stt_final_fallback_seconds,
        )
        stt_final_fallback.register()
        ctx.add_shutdown_callback(stt_final_fallback.aclose)
    event_log = SessionEventLog(
        enabled=settings.livekit_debug_event_log,
        include_transcripts=settings.livekit_debug_transcripts,
        directory=settings.livekit_debug_log_dir,
        userdata=userdata,
        room_name=ctx.room.name,
    )
    await event_log.start()
    LiveKitSessionObserver(event_log).register(session)
    ctx.add_shutdown_callback(event_log.close)
    event_log.emit(
        "session_configured",
        stt_model=settings.livekit_stt_model,
        stt_language=settings.livekit_stt_language,
        llm_model=settings.livekit_llm_model,
        tts_model=settings.livekit_tts_model,
        tts_voice=settings.livekit_tts_voice,
        tts_language=settings.livekit_tts_language,
        turn_detection=settings.livekit_turn_detection,
        endpointing_mode=settings.livekit_endpointing_mode,
        endpointing_min_delay=settings.livekit_endpointing_min_delay_seconds,
        endpointing_max_delay=settings.livekit_endpointing_max_delay_seconds,
        interruption_mode=settings.livekit_interruption_mode,
        interruption_min_duration=settings.livekit_interruption_min_duration_seconds,
        interruption_min_words=settings.livekit_interruption_min_words,
        preemptive_generation_enabled=False,
        stt_final_fallback_enabled=stt_final_fallback is not None,
        stt_final_fallback_seconds=(
            settings.livekit_stt_final_fallback_seconds if stt_final_fallback is not None else None
        ),
        transcript_rewrite_enabled=transcript_rewriter is not None,
        transcript_rewrite_disabled_reason=transcript_rewrite_disabled_reason,
        transcript_rewrite_model=(
            transcript_rewriter.model if transcript_rewriter is not None else None
        ),
        transcript_rewrite_timeout_seconds=(
            transcript_rewriter.timeout_seconds if transcript_rewriter is not None else None
        ),
        transcript_rewrite_context_window_turns=(
            transcript_rewriter.context_window_turns if transcript_rewriter is not None else None
        ),
        transcript_rewrite_memory_max_corrections=(
            transcript_rewriter.memory_max_corrections if transcript_rewriter is not None else None
        ),
    )
    await session.start(
        room=ctx.room,
        agent=AloSMAgent(
            state_store=state_store,
            session_data=userdata,
            transcript_rewriter=transcript_rewriter,
            transcript_rewrite_publisher=lambda item_id, result: publish_transcript_rewrite(
                session,
                item_id,
                result,
            ),
        ),
        record=settings.livekit_record_audio,
        room_options=RoomOptions(
            text_input=True,
            audio_input=AudioInputOptions(
                # Native LiveKit input processing. Enhanced cancellation remains
                # opt-in because its plugin is separately metered and not installed.
                auto_gain_control=True,
                pre_connect_audio=True,
            ),
            close_on_disconnect=True,
            delete_room_on_close=True,
        ),
    )
    await publish_booking_state(session)
    session.generate_reply(
        instructions=(
            "Nói ngắn gọn rằng đã khôi phục yêu cầu đặt xe trước đó. Tóm tắt đúng trạng thái này: "
            f"{userdata.booking_draft.conversation_summary()}. Sau đó hỏi khách có muốn tiếp tục không."
            if recovered
            else "Chào khách bằng tiếng Việt, giới thiệu ngắn gọn bạn là tổng đài AloSM "
            "và mời khách cho biết yêu cầu đặt xe."
        ),
        # Do not discard an early user utterance while the greeting is playing.
        allow_interruptions=True,
    )


if __name__ == "__main__":
    cli.run_app(server)
