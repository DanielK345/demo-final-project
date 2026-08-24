"""Exercise a real LiveKit Room and record one privacy-safe result per attempt.

The script uses LiveKit's RTC client as the simulated participant. It does not
replace Room/WebRTC, agent dispatch, AgentSession, or any media pipeline node.

Run while the ``alosm-voice`` worker is registered::

    uv run python -m scripts.livekit_room_smoke --runs 30
    uv run python -m scripts.livekit_room_smoke --runs 5 --booking

Credentials and JWTs are never printed or written to the result artifact.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from livekit import rtc

from src.backend.repositories.persistence_repository import PersistenceRepository
from src.voice_agent.config import LiveKitVoiceSettings, get_livekit_voice_settings
from src.voice_agent.state_sync import BOOKING_STATE_TOPIC
from src.voice_agent.tokens import issue_connection_details


async def _select_location_with_clarification(
    *,
    target: str,
    selection_text: str,
    clarification_text: str,
    send_turn: Callable[[str], Awaitable[None]],
    current_state: Callable[[], dict[str, object]],
) -> None:
    """Complete a multi-turn LiveKit AgentTask location selection.

    An AgentTask may search on one turn and ask the participant to confirm a
    candidate on the next. The smoke participant therefore answers that native
    conversational turn instead of assuming the LLM will chain every tool call
    in one response.
    """

    await send_turn(selection_text)
    if current_state().get(target) is not None:
        return

    await send_turn(clarification_text)
    if current_state().get(target) is None:
        raise TimeoutError(f"{target} was not selected after clarification")


async def _request_quote_confirmation(
    *,
    send_turn: Callable[[str], Awaitable[None]],
    current_state: Callable[[], dict[str, object]],
) -> None:
    """Give a multi-turn AgentTask one explicit turn to finish the quote."""

    state = current_state()
    if state.get("quote") is not None and state.get("confirmation_status") == "awaiting":
        return

    await send_turn("Hai địa điểm đã đúng. Hãy báo giá và đọc lại chuyến để tôi xác nhận.")
    state = current_state()
    if state.get("quote") is None or state.get("confirmation_status") != "awaiting":
        raise TimeoutError("booking quote was not prepared after an explicit follow-up turn")


@dataclass
class SmokeAttemptResult:
    """Machine-readable outcome for one isolated LiveKit Room attempt."""

    schema_version: str
    run_number: int
    call_id: str
    app_session_id: str
    started_at: str
    input_mode: str
    booking_enabled: bool
    status: str = "failed"
    failure_stage: str | None = None
    error_type: str | None = None
    duration_ms: float | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    booking_ids: list[str] = field(default_factory=list)
    confirmation_status_at_booking: str | None = None


def _durable_booking_checks(
    *,
    session_id: str,
    user_id: str,
    quote_id: str,
    booking_id: str,
    session_row: dict[str, object] | None,
    quote_row: dict[str, object] | None,
    booking_row: dict[str, object] | None,
) -> dict[str, bool]:
    """Return release checks from authoritative rows, never from transcript text."""

    return {
        "durable_session_exists": session_row is not None,
        "durable_session_ended": bool(session_row and session_row.get("status") == "ENDED"),
        "durable_session_booking_matches": bool(
            session_row
            and session_row.get("booking_id") == booking_id
            and session_row.get("booking_lifecycle_status") == "SUCCESS"
            and session_row.get("confirmation_status") == "confirmed"
        ),
        "durable_state_advanced": bool(
            session_row and isinstance(session_row.get("voice_state_revision"), int)
            and int(session_row["voice_state_revision"]) > 0
        ),
        "durable_quote_matches": bool(
            quote_row
            and quote_row.get("quote_id") == quote_id
            and quote_row.get("session_id") == session_id
            and quote_row.get("user_id") == user_id
            and quote_row.get("status") == "CONSUMED"
        ),
        "durable_booking_matches": bool(
            booking_row
            and booking_row.get("booking_id") == booking_id
            and booking_row.get("quote_id") == quote_id
            and booking_row.get("session_id") == session_id
            and booking_row.get("user_id") == user_id
        ),
    }


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="milliseconds")


def _default_output_path() -> Path:
    run_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("reports") / "voice-evaluation" / "smoke" / run_id / "connection-results.jsonl"


def _append_result(path: Path, result: SmokeAttemptResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(asdict(result), ensure_ascii=False, separators=(",", ":")) + "\n")


async def run_smoke_attempt(
    settings: LiveKitVoiceSettings,
    *,
    run_number: int,
    booking: bool = False,
) -> SmokeAttemptResult:
    """Run one Room attempt and return a result even when the attempt fails."""

    attempt_started = time.monotonic()
    call_id = str(uuid4())
    app_session_id = f"livekit-smoke-{uuid4().hex}"
    user_id = "livekit-smoke-user"
    repository: PersistenceRepository | None = None
    result = SmokeAttemptResult(
        schema_version="2",
        run_number=run_number,
        call_id=call_id,
        app_session_id=app_session_id,
        started_at=_utc_now(),
        # Booking turns are published through LiveKit's native text input. This
        # run validates RTC/AgentTask behavior, not STT transcript-final quality.
        input_mode="livekit_text",
        booking_enabled=booking,
    )
    marks: dict[str, float] = {}
    current_stage = "issue_credentials"

    def mark(name: str) -> None:
        marks.setdefault(name, time.monotonic())

    try:
        if booking:
            current_stage = "prepare_durable_session"
            repository = PersistenceRepository()
            smoke_user = await repository.ensure_voice_guest("+84000000000")
            durable_session = await repository.create_session(
                user_id=str(smoke_user["user_id"]),
                channel="LIVEKIT_SMOKE",
                device_id="smoke-runner",
                phone=None,
            )
            user_id = str(smoke_user["user_id"])
            app_session_id = str(durable_session["session_id"])
            result.app_session_id = app_session_id

        current_stage = "issue_credentials"
        details = issue_connection_details(
            settings,
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_id,
        )
        mark("credentials_issued")
    except Exception as exc:
        result.failure_stage = current_stage
        result.error_type = type(exc).__name__
        result.duration_ms = round((time.monotonic() - attempt_started) * 1000, 3)
        return result

    room = rtc.Room()
    agent_joined = asyncio.Event()
    agent_audio = asyncio.Event()
    agent_listening = asyncio.Event()
    agent_speaking = asyncio.Event()
    booking_state_received = asyncio.Event()
    booking_state_updated = asyncio.Event()
    booking_result_audio = asyncio.Event()
    latest_booking_state: dict[str, object] = {}
    booking_ids: list[str] = []
    confirmation_status_at_booking: str | None = None
    agent_is_speaking = False
    audio_tasks: set[asyncio.Task[None]] = set()

    async def wait_for_audio_frame(track: rtc.RemoteAudioTrack) -> None:
        stream = rtc.AudioStream(track)
        try:
            async for _event in stream:
                # A subscribed LiveKit audio track can yield frames before the
                # agent is speaking. Count only frames observed after the SDK's
                # native agent-state transition, without inspecting raw audio.
                if agent_is_speaking:
                    mark("first_agent_audio")
                    agent_audio.set()
                if agent_is_speaking and latest_booking_state.get("booking") is not None:
                    mark("booking_result_audio")
                    booking_result_audio.set()
        finally:
            await stream.aclose()

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            mark("agent_joined")
            agent_joined.set()
            if participant.attributes.get("lk.agent.state") in {"idle", "listening"}:
                mark("agent_listening")
                agent_listening.set()

    @room.on("participant_attributes_changed")
    def on_participant_attributes_changed(
        changed_attributes: dict[str, str],
        participant: rtc.Participant,
    ) -> None:
        nonlocal agent_is_speaking
        del participant
        state = changed_attributes.get("lk.agent.state")
        if state == "speaking":
            agent_is_speaking = True
            mark("agent_speaking")
            agent_speaking.set()
            agent_listening.clear()
        elif state in {"idle", "listening"}:
            agent_is_speaking = False
            mark("agent_listening")
            agent_listening.set()

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if isinstance(track, rtc.RemoteAudioTrack) and participant.identity:
            task = asyncio.create_task(wait_for_audio_frame(track))
            audio_tasks.add(task)
            task.add_done_callback(audio_tasks.discard)

    @room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        nonlocal confirmation_status_at_booking, latest_booking_state
        if packet.topic != BOOKING_STATE_TOPIC:
            return
        try:
            state = json.loads(packet.data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(state, dict) or state.get("schema_version") != "1":
            return
        latest_booking_state = state
        mark("booking_state_received")
        booking_state_received.set()
        booking_state_updated.set()
        booking_state = state.get("booking")
        if isinstance(booking_state, dict) and isinstance(booking_state.get("booking_id"), str):
            booking_id = booking_state["booking_id"]
            if booking_id not in booking_ids:
                booking_ids.append(booking_id)
            if confirmation_status_at_booking is None:
                raw_status = state.get("confirmation_status")
                confirmation_status_at_booking = str(raw_status) if raw_status is not None else None
            mark("booking_completed")

    async def wait_for_booking_state(
        predicate: Callable[[dict[str, object]], bool],
        *,
        timeout: float = 90,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout
        while not predicate(latest_booking_state):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("booking state predicate timed out")
            booking_state_updated.clear()
            await asyncio.wait_for(booking_state_updated.wait(), timeout=remaining)
        return latest_booking_state

    async def send_booking_turn(text: str, *, timeout: float = 45) -> None:
        """Send one native LiveKit text turn and wait until the AgentTask yields."""

        agent_listening.clear()
        await room.local_participant.send_text(text, topic="lk.chat")
        await asyncio.wait_for(agent_listening.wait(), timeout=timeout)

    async def run_booking_happy_path() -> None:
        nonlocal current_stage

        current_stage = "booking_request"
        await send_booking_turn("Tôi muốn đặt xe 4 chỗ từ VinUni đến Hồ Gươm.")
        await wait_for_booking_state(
            lambda state: int(state.get("revision", 0)) >= 1,
            timeout=5,
        )

        current_stage = "pickup_selection"
        await _select_location_with_clarification(
            target="pickup",
            selection_text="Tôi chọn Cổng chính VinUni làm điểm đón và xe 4 chỗ.",
            clarification_text="Đúng, tôi xác nhận chọn Cổng chính VinUni làm điểm đón.",
            send_turn=send_booking_turn,
            current_state=lambda: latest_booking_state,
        )
        result.checks["pickup_selected"] = True

        current_stage = "destination_selection"
        await _select_location_with_clarification(
            target="destination",
            selection_text="Tôi chọn Bưu điện Hà Nội làm điểm đến.",
            clarification_text="Đúng, tôi xác nhận chọn Bưu điện Hà Nội làm điểm đến.",
            send_turn=send_booking_turn,
            current_state=lambda: latest_booking_state,
        )
        result.checks["destination_selected"] = True

        current_stage = "quote_confirmation"
        await _request_quote_confirmation(
            send_turn=send_booking_turn,
            current_state=lambda: latest_booking_state,
        )
        result.checks["quote_confirmation_requested"] = True

        current_stage = "booking_creation"
        agent_listening.clear()
        await room.local_participant.send_text("Tôi xác nhận đặt chuyến này.", topic="lk.chat")
        completed = await wait_for_booking_state(lambda state: state.get("booking") is not None)
        booking_state = completed.get("booking")
        if not isinstance(booking_state, dict):
            raise RuntimeError("missing booking result")
        if not str(booking_state.get("booking_id", "")).startswith("book_"):
            raise RuntimeError("unexpected durable booking id")

        current_stage = "booking_result_audio"
        await asyncio.wait_for(booking_result_audio.wait(), timeout=45)

    try:
        current_stage = "room_connect"
        await room.connect(details.server_url, details.participant_token)
        mark("room_connected")
        result.checks["room_connected"] = True

        current_stage = "agent_join"
        await asyncio.wait_for(agent_joined.wait(), timeout=30)
        result.checks["agent_joined"] = True

        current_stage = "agent_audio"
        await asyncio.wait_for(agent_audio.wait(), timeout=45)
        result.checks["agent_audio"] = True
        result.checks["agent_spoke"] = agent_speaking.is_set()

        current_stage = "booking_state"
        await asyncio.wait_for(booking_state_received.wait(), timeout=15)
        result.checks["booking_state_received"] = True

        current_stage = "greeting_complete"
        await asyncio.wait_for(agent_listening.wait(), timeout=45)
        mark("greeting_completed")
        result.checks["greeting_completed"] = True

        if booking:
            current_stage = "booking_flow"
            await run_booking_happy_path()
            result.checks["booking_completed"] = True
            result.checks["booking_result_audio"] = True

            current_stage = "durable_verification"
            booking_state = latest_booking_state.get("booking")
            quote_state = latest_booking_state.get("quote")
            if not isinstance(booking_state, dict) or not isinstance(quote_state, dict) or repository is None:
                raise RuntimeError("missing durable booking verification context")
            booking_id = str(booking_state.get("booking_id") or "")
            quote_id = str(quote_state.get("quote_id") or "")
            session_row, quote_row, booking_row = await asyncio.gather(
                repository.get_session(app_session_id),
                repository.get_quote(quote_id),
                repository.booking(booking_id),
            )
            durable_checks = _durable_booking_checks(
                session_id=app_session_id,
                user_id=user_id,
                quote_id=quote_id,
                booking_id=booking_id,
                session_row=session_row,
                quote_row=quote_row,
                booking_row=booking_row,
            )
            result.checks.update(durable_checks)
            if not all(durable_checks.values()):
                raise RuntimeError("durable booking rows did not match LiveKit state")
            mark("durable_booking_verified")

        result.status = "passed"
    except Exception as exc:
        result.failure_stage = current_stage
        result.error_type = type(exc).__name__
    finally:
        for task in tuple(audio_tasks):
            task.cancel()
        try:
            await asyncio.wait_for(room.disconnect(), timeout=5.0)
        except Exception:
            pass

    result.booking_ids = booking_ids
    result.confirmation_status_at_booking = confirmation_status_at_booking
    result.checks["booking_requires_confirmation"] = not booking_ids or (confirmation_status_at_booking == "confirmed")
    result.checks["single_booking_id"] = len(booking_ids) <= 1
    if result.status == "passed" and not all(
        (
            result.checks["booking_requires_confirmation"],
            result.checks["single_booking_id"],
        )
    ):
        result.status = "failed"
        result.failure_stage = "business_invariant"
        result.error_type = "BusinessInvariantViolation"
    result.duration_ms = round((time.monotonic() - attempt_started) * 1000, 3)
    for name, timestamp in marks.items():
        result.timings_ms[name] = round((timestamp - attempt_started) * 1000, 3)
    return result


async def run_smoke(
    *,
    booking: bool = False,
    runs: int = 1,
    start_run: int = 1,
    output: Path | None = None,
) -> list[SmokeAttemptResult]:
    """Run isolated attempts sequentially and persist every pass or failure."""

    if runs < 1:
        raise ValueError("runs must be at least 1")
    settings = get_livekit_voice_settings()
    settings.require_configured()
    output_path = output or _default_output_path()
    results: list[SmokeAttemptResult] = []

    for run_number in range(start_run, start_run + runs):
        result = await run_smoke_attempt(settings, run_number=run_number, booking=booking)
        _append_result(output_path, result)
        results.append(result)
        stage = result.failure_stage or "complete"
        print(f"LIVEKIT_SMOKE_RUN={run_number}/{start_run + runs - 1} STATUS={result.status.upper()} STAGE={stage}")

    passed = sum(result.status == "passed" for result in results)
    print(f"LIVEKIT_SMOKE_SUMMARY={passed}/{runs} OUTPUT={output_path}")
    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--booking", action="store_true", help="Run the real LLM booking happy path")
    parser.add_argument("--runs", type=int, default=1, help="Number of isolated sequential attempts")
    parser.add_argument("--start-run", type=int, default=1, help="Starting run number")
    parser.add_argument("--output", type=Path, help="JSONL output path; defaults under reports/")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    attempt_results = asyncio.run(
        run_smoke(booking=args.booking, runs=args.runs, start_run=args.start_run, output=args.output)
    )
    if any(result.status != "passed" for result in attempt_results):
        raise SystemExit(1)
