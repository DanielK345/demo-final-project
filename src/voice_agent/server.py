"""LiveKit AgentServer worker for the AloSM voice runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    llm,
    stt,
    tts,
    vad,
)
from livekit.agents.voice.events import ErrorEvent
from livekit.agents.voice.room_io import AudioInputOptions, RoomOptions

from src.backend.services.handoff_service import HandoffService
from src.backend.services.knowledge_service import KnowledgeService
from src.backend.services.pricing_service import PricingService
from src.voice_agent.agent import AloSMAgent
from src.voice_agent.config import LiveKitVoiceSettings, get_livekit_voice_settings
from src.voice_agent.model_factory import build_stt
from src.voice_agent.observability import LiveKitSessionObserver, SessionEventLog
from src.voice_agent.persistence import DatabaseVoiceStateStore, VoiceStateStore
from src.voice_agent.session_data import AloSMSessionData, FailureCode, FallbackAction, HandoffState
from src.voice_agent.state_sync import publish_booking_state
from src.voice_agent.tts_text import vietnamese_currency_tts_transform

logger = logging.getLogger(__name__)

_STATE_STORE_KEY = "alosm_voice_state_store"
_PROCESS_STORE_READY_KEY = "alosm_process_store_ready"
_PREWARMED_VAD_KEY = "alosm_prewarmed_vad"
_PREWARMED_STT_KEY = "alosm_prewarmed_stt"
_PREWARMED_KNOWLEDGE_KEY = "alosm_prewarmed_knowledge"
_PREWARMED_PRICING_KEY = "alosm_prewarmed_pricing"


def _build_llm(settings: LiveKitVoiceSettings):
    """Build an LLM through a supported LiveKit provider integration."""

    if settings.livekit_llm_provider == "openai":
        try:
            from livekit.plugins import openai
        except ImportError as exc:  # pragma: no cover - depends on optional plugin
            raise RuntimeError("LIVEKIT_LLM_PROVIDER=openai requires the livekit-plugins-openai package.") from exc
        # The repository currently pins OpenAI SDK 2.20 through aider-chat.
        # Plugin 1.5's Responses event schema is no longer compatible with the
        # current OpenAI wire response, while Chat Completions remains supported
        # and preserves LiveKit function-tool behavior.
        return openai.LLM(
            model=settings.livekit_llm_model,
            api_key=settings.openai_api_key.get_secret_value(),
            # Booking tools mutate one revisioned business document. LiveKit's
            # documented serial tool loop prevents independent calls from racing
            # the optimistic state revision.
            parallel_tool_calls=False,
        )

    return inference.LLM(
        model=settings.livekit_llm_model,
        api_key=settings.livekit_api_key.get_secret_value(),
        api_secret=settings.livekit_api_secret.get_secret_value(),
        extra_kwargs={"parallel_tool_calls": False},
    )


def _build_tts(settings: LiveKitVoiceSettings):
    """Build TTS through LiveKit Inference or its official OpenAI plugin."""

    if settings.livekit_tts_provider == "openai":
        try:
            from livekit.plugins import openai
        except ImportError as exc:  # pragma: no cover - depends on optional plugin
            raise RuntimeError("LIVEKIT_TTS_PROVIDER=openai requires the livekit-plugins-openai package.") from exc
        return openai.TTS(
            model=settings.livekit_tts_model,
            voice=settings.livekit_tts_voice,
            api_key=settings.openai_api_key.get_secret_value(),
            instructions="Nói tiếng Việt tự nhiên, rõ ràng, thân thiện và với âm lượng ổn định.",
        )

    return inference.TTS(
        model=settings.livekit_tts_model,
        voice=settings.livekit_tts_voice,
        language=settings.livekit_tts_language,
        api_key=settings.livekit_api_key.get_secret_value(),
        api_secret=settings.livekit_api_secret.get_secret_value(),
    )


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
    vad_model: vad.VAD | None = None,
    stt_model: stt.STT | None = None,
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
    return AgentSession(
        userdata=userdata,
        vad=vad_model if vad_model is not None else inference.VAD(model="silero"),
        stt=stt_model if stt_model is not None else build_stt(settings),
        llm=_build_llm(settings),
        tts=_build_tts(settings),
        tts_text_transforms=[
            "filter_emoji",
            "filter_markdown",
            vietnamese_currency_tts_transform,
        ],
        transcription_timeout=settings.livekit_transcription_timeout_seconds,
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
        user_id=participant_identity,
        participant_identity=participant_identity,
        consent_granted=True,
        recording_enabled=settings.livekit_record_audio,
        critical_confidence_threshold=settings.livekit_critical_confidence_threshold,
    )


async def restore_session_data(
    userdata: AloSMSessionData,
    state_store: VoiceStateStore,
    *,
    timeout_seconds: float | None = None,
) -> bool:
    """Restore a draft before AgentSession starts, with an explicit safe fallback."""

    try:
        async with asyncio.timeout(timeout_seconds):
            recovered = await state_store.restore(userdata)
        return recovered
    except Exception:
        logger.exception("failed to restore LiveKit voice state")
        # A timed-out store is not safe for later writes in the same call. Keep
        # the conversation available in memory and avoid blocking every tool turn.
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
) -> Callable[[], Awaitable[None]]:
    """Map native LiveKit provider errors to the public recovery contract."""

    failure_lock = asyncio.Lock()
    failure_tasks: set[asyncio.Task[None]] = set()

    async def persist_failure(event: ErrorEvent) -> None:
        # LiveKit already retries errors marked recoverable. Publishing those as
        # customer-facing failures makes a healthy retry look like an outage.
        if bool(getattr(event.error, "recoverable", False)):
            logger.info("LiveKit provider retry in progress source=%s", type(event.source).__name__)
            return

        # Follow LiveKit's documented continuation strategy. LLM/TTS instances
        # are recreated on the next turn; STT owns a long-lived stream and needs
        # the current Agent re-applied to restart it. Text input remains available
        # through RoomIO while the customer sees the typed fallback state.
        if isinstance(event.source, stt.STT):
            current_agent = session.current_agent
            if current_agent is not None:
                session.update_agent(current_agent)
            event.error.recoverable = True
        elif isinstance(event.source, (llm.LLM, tts.TTS)):
            event.error.recoverable = True

        async with failure_lock:
            code, message, fallback = _provider_failure(event)
            session.userdata.record_failure(code, message, fallback_action=fallback)
            try:
                await state_store.save(session.userdata)
            except Exception:
                logger.exception("failed to persist LiveKit provider failure")
            await publish_booking_state(session)

    @session.on("error")
    def on_error(event: ErrorEvent) -> None:
        task = asyncio.create_task(persist_failure(event))
        failure_tasks.add(task)
        task.add_done_callback(failure_tasks.discard)

    async def drain_failure_tasks() -> None:
        if failure_tasks:
            await asyncio.gather(*tuple(failure_tasks), return_exceptions=True)

    return drain_failure_tasks


_server_settings = get_livekit_voice_settings()
server = AgentServer(
    ws_url=_server_settings.livekit_url or None,
    api_key=_server_settings.livekit_api_key.get_secret_value() or None,
    api_secret=_server_settings.livekit_api_secret.get_secret_value() or None,
    num_idle_processes=_server_settings.livekit_num_idle_processes,
)


def prepare_process(proc: JobProcess) -> None:
    """Prewarm process-local model and state resources before job assignment."""

    # AgentServer 1.6.6 invokes setup_fnc synchronously before creating the job
    # event loop. Do not open asyncpg connections here: pooled asyncio connections
    # cannot be transferred to the different loop used by the RTC job.
    proc.userdata[_STATE_STORE_KEY] = DatabaseVoiceStateStore()
    # LiveKit keeps idle job processes warm specifically so model/plugin setup is
    # not paid after a participant is waiting. Google STT's module import and ADC
    # resolution are synchronous and safe to perform here; its streaming client
    # is still opened later on the RTC job's event loop.
    proc.userdata[_PREWARMED_VAD_KEY] = inference.VAD(model="silero")
    proc.userdata[_PREWARMED_STT_KEY] = build_stt(_server_settings)
    # Policy and pricing catalogs are local, validated and static for the
    # process lifetime. Load them during LiveKit prewarm so a FAQ turn never
    # adds file I/O or catalog validation latency to the first user request.
    proc.userdata[_PREWARMED_KNOWLEDGE_KEY] = KnowledgeService()
    proc.userdata[_PREWARMED_PRICING_KEY] = PricingService()
    proc.userdata[_PROCESS_STORE_READY_KEY] = True


server.setup_fnc = prepare_process


def _process_state_store(ctx: JobContext) -> DatabaseVoiceStateStore:
    state_store = ctx.proc.userdata.get(_STATE_STORE_KEY)
    return state_store if isinstance(state_store, DatabaseVoiceStateStore) else DatabaseVoiceStateStore()


def _process_vad(ctx: JobContext) -> vad.VAD | None:
    model = ctx.proc.userdata.get(_PREWARMED_VAD_KEY)
    return model if isinstance(model, vad.VAD) else None


def _process_stt(ctx: JobContext) -> stt.STT | None:
    model = ctx.proc.userdata.get(_PREWARMED_STT_KEY)
    return model if isinstance(model, stt.STT) else None


def _process_knowledge(ctx: JobContext) -> KnowledgeService | None:
    service = ctx.proc.userdata.get(_PREWARMED_KNOWLEDGE_KEY)
    return service if isinstance(service, KnowledgeService) else None


def _process_pricing(ctx: JobContext) -> PricingService | None:
    service = ctx.proc.userdata.get(_PREWARMED_PRICING_KEY)
    return service if isinstance(service, PricingService) else None


async def _timed_restore(
    userdata: AloSMSessionData,
    state_store: VoiceStateStore,
    timeout_seconds: float,
) -> tuple[bool, float]:
    started = time.monotonic()
    recovered = await restore_session_data(
        userdata,
        state_store,
        timeout_seconds=timeout_seconds,
    )
    return recovered, round((time.monotonic() - started) * 1000, 3)


def request_initial_greeting(
    session: AgentSession[AloSMSessionData],
    *,
    recovered: bool,
) -> None:
    """Schedule a native greeting without an unnecessary LLM turn for new calls."""

    if recovered:
        session.generate_reply(
            instructions=(
                "Nói ngắn gọn rằng đã khôi phục yêu cầu đặt xe trước đó. Tóm tắt đúng trạng thái này: "
                f"{session.userdata.booking_draft.conversation_summary()}. "
                "Sau đó hỏi khách có muốn tiếp tục không."
            ),
            allow_interruptions=True,
        )
        return

    session.say(
        "Chào bạn, tôi là tổng đài viên AloSM. Bạn vui lòng cho biết yêu cầu đặt xe của mình nhé?",
        allow_interruptions=True,
    )


def register_operator_takeover(
    session: AgentSession[AloSMSessionData],
    state_store: VoiceStateStore,
) -> Callable[[], Awaitable[None]]:
    """Stop the AI when an authenticated operator joins the active Room.

    The operator is a normal LiveKit participant with trusted metadata. The
    backend still owns role/acceptance checks; this hook only reacts to the
    participant that was allowed into the Room and hands media control over.
    """

    takeover_lock = asyncio.Lock()
    takeover_tasks: set[asyncio.Task[None]] = set()
    takeover_started = False

    async def takeover(participant: object) -> None:
        nonlocal takeover_started
        metadata_raw = str(getattr(participant, "metadata", "") or "")
        try:
            metadata = json.loads(metadata_raw)
        except (TypeError, json.JSONDecodeError):
            return
        if metadata.get("role") != "operator":
            return
        handoff_id = str(metadata.get("handoff_id") or "")
        operator_id = str(metadata.get("operator_id") or "")
        current = session.userdata.handoff
        if not handoff_id or not operator_id or current is None or current.handoff_id != handoff_id:
            return
        async with takeover_lock:
            if takeover_started:
                return
            takeover_started = True
            try:
                await HandoffService().connect_handoff_durable(handoff_id, operator_id)
            except Exception:
                logger.exception("failed to mark operator handoff connected id=%s", handoff_id)
            session.userdata.handoff = HandoffState(
                handoff_id=handoff_id,
                status="connected",
                reason_code=current.reason_code,
                operator_id=operator_id,
                room_name=current.room_name or session.room_io.room.name,
            )
            await state_store.save(session.userdata)
            await publish_booking_state(session)
            session.interrupt()
            session.input.set_audio_enabled(False)
            session.output.set_audio_enabled(False)
            # LiveKit keeps the customer and operator in the Room after the
            # agent session shuts down; this prevents the AI from hearing or
            # speaking over the human takeover.
            session.shutdown(drain=False)

    def on_participant_connected(participant: object) -> None:
        task = asyncio.create_task(takeover(participant))
        takeover_tasks.add(task)
        task.add_done_callback(takeover_tasks.discard)

    session.room_io.room.on("participant_connected", on_participant_connected)
    for participant in session.room_io.room.remote_participants.values():
        on_participant_connected(participant)

    async def drain() -> None:
        current_task = asyncio.current_task()
        pending = tuple(task for task in takeover_tasks if task is not current_task)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    return drain


@server.rtc_session(agent_name=get_livekit_voice_settings().livekit_agent_name)
async def alosm_voice_session(ctx: JobContext) -> None:
    """Run one LiveKit AgentSession for one Room call."""

    settings = get_livekit_voice_settings()
    userdata = build_session_data(ctx, settings)
    event_log = SessionEventLog(
        enabled=settings.livekit_debug_event_log,
        include_transcripts=settings.livekit_debug_transcripts,
        directory=settings.livekit_debug_log_dir,
        userdata=userdata,
        room_name=ctx.room.name,
    )
    await event_log.start()
    ctx.add_shutdown_callback(event_log.close)
    event_log.emit("worker_milestone", milestone="job_entry")

    state_store = _process_state_store(ctx)
    knowledge_service = _process_knowledge(ctx)
    pricing_service = _process_pricing(ctx)
    event_log.emit(
        "worker_milestone",
        milestone="process_setup_status",
        state_store_ready=bool(ctx.proc.userdata.get(_PROCESS_STORE_READY_KEY)),
        vad_prewarmed=_process_vad(ctx) is not None,
        stt_prewarmed=_process_stt(ctx) is not None,
        knowledge_prewarmed=knowledge_service is not None,
        pricing_prewarmed=pricing_service is not None,
    )
    restore_task = asyncio.create_task(
        _timed_restore(
            userdata,
            state_store,
            settings.livekit_state_restore_timeout_seconds,
        ),
        name=f"restore-voice-state-{userdata.call_id}",
    )
    # Let asyncpg begin checkout/query I/O, then construct the LiveKit pipeline
    # while that network operation is in flight. The Agent itself is created only
    # after restore completes, preserving its recovered-context instructions.
    await asyncio.sleep(0)
    session_build_started = time.monotonic()
    try:
        session = build_agent_session(
            settings,
            userdata=userdata,
            vad_model=_process_vad(ctx),
            stt_model=_process_stt(ctx),
        )
    except BaseException:
        restore_task.cancel()
        await asyncio.gather(restore_task, return_exceptions=True)
        raise
    event_log.emit(
        "worker_milestone",
        milestone="agent_session_built",
        duration_ms=round((time.monotonic() - session_build_started) * 1000, 3),
    )
    recovered, restore_duration_ms = await restore_task
    event_log.emit(
        "worker_milestone",
        milestone="state_restore_completed",
        duration_ms=restore_duration_ms,
        recovered=recovered,
        persistence_enabled=userdata.persistence_enabled,
    )
    drain_provider_failures = register_provider_failure_sync(session, state_store)
    ctx.add_shutdown_callback(drain_provider_failures)
    LiveKitSessionObserver(event_log).register(session)
    event_log.emit(
        "session_configured",
        stt_model=settings.livekit_stt_model,
        stt_language=settings.livekit_stt_language,
        llm_provider=settings.livekit_llm_provider,
        llm_model=settings.livekit_llm_model,
        tts_provider=settings.livekit_tts_provider,
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
        transcription_timeout=settings.livekit_transcription_timeout_seconds,
        policy_catalog_version=(
            knowledge_service.retriever.catalog.catalog_version if knowledge_service is not None else None
        ),
        pricing_catalog_version=pricing_service.catalog.version if pricing_service is not None else None,
    )
    session_start_started = time.monotonic()
    event_log.emit("worker_milestone", milestone="session_start_called")
    await session.start(
        room=ctx.room,
        agent=AloSMAgent(
            state_store=state_store,
            session_data=userdata,
            knowledge_service=knowledge_service,
            pricing_service=pricing_service,
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
            delete_room_on_close=settings.livekit_delete_room_on_close,
        ),
    )
    event_log.emit(
        "worker_milestone",
        milestone="session_started",
        duration_ms=round((time.monotonic() - session_start_started) * 1000, 3),
    )
    drain_operator_takeover = register_operator_takeover(session, state_store)
    ctx.add_shutdown_callback(drain_operator_takeover)
    await publish_booking_state(session)
    event_log.emit("worker_milestone", milestone="initial_state_published")
    request_initial_greeting(session, recovered=recovered)
    event_log.emit("worker_milestone", milestone="greeting_requested")


if __name__ == "__main__":
    cli.run_app(server)
