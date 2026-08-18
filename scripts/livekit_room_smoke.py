"""Connect a real RTC participant and verify agent join plus outbound audio.

This script never prints credentials or JWTs. Run it while the AloSM LiveKit worker
is registered:

    uv run python -m scripts.livekit_room_smoke
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Callable
from uuid import uuid4

from livekit import rtc

from src.voice_agent.config import get_livekit_voice_settings
from src.voice_agent.state_sync import BOOKING_STATE_TOPIC
from src.voice_agent.tokens import issue_connection_details


async def run_smoke(*, booking: bool = False) -> None:
    settings = get_livekit_voice_settings()
    settings.require_configured()
    details = issue_connection_details(
        settings,
        user_id="livekit-smoke-user",
        app_session_id=f"livekit-smoke-{uuid4().hex}",
        call_instance_id=str(uuid4()),
    )

    room = rtc.Room()
    agent_joined = asyncio.Event()
    agent_audio = asyncio.Event()
    agent_listening = asyncio.Event()
    agent_speaking = asyncio.Event()
    booking_state_received = asyncio.Event()
    booking_state_updated = asyncio.Event()
    booking_result_audio = asyncio.Event()
    latest_booking_state: dict[str, object] = {}
    audio_tasks: set[asyncio.Task[None]] = set()

    async def wait_for_audio_frame(track: rtc.RemoteAudioTrack) -> None:
        stream = rtc.AudioStream(track)
        try:
            async for _event in stream:
                agent_audio.set()
                if latest_booking_state.get("booking") is not None:
                    booking_result_audio.set()
        finally:
            await stream.aclose()

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        if participant.identity.startswith("agent-") or participant.name:
            agent_joined.set()
            if participant.attributes.get("lk.agent.state") in {"idle", "listening"}:
                agent_listening.set()

    @room.on("participant_attributes_changed")
    def on_participant_attributes_changed(
        changed_attributes: dict[str, str],
        participant: rtc.Participant,
    ) -> None:
        state = changed_attributes.get("lk.agent.state")
        if state == "speaking":
            agent_speaking.set()
            agent_listening.clear()
        elif state in {"idle", "listening"}:
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
        nonlocal latest_booking_state
        if packet.topic != BOOKING_STATE_TOPIC:
            return
        try:
            state = json.loads(packet.data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if state.get("schema_version") == "1":
            latest_booking_state = state
            booking_state_received.set()
            booking_state_updated.set()

    async def wait_for_booking_state(
        predicate: Callable[[dict[str, object]], bool],
        *,
        timeout: float = 90,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout
        while not predicate(latest_booking_state):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"booking state predicate timed out: {latest_booking_state}")
            booking_state_updated.clear()
            await asyncio.wait_for(booking_state_updated.wait(), timeout=remaining)
        return latest_booking_state

    async def run_booking_happy_path() -> None:
        await room.local_participant.send_text(
            "Tôi muốn đặt xe 4 chỗ từ VinUni đến Hồ Gươm.",
            topic="lk.chat",
        )
        await wait_for_booking_state(
            lambda state: state.get("vehicle_type") == "CAR_4"
            and int(state.get("revision", 0)) >= 2
        )

        await room.local_participant.send_text(
            "Tôi chọn Cổng chính VinUni làm điểm đón.",
            topic="lk.chat",
        )
        await wait_for_booking_state(lambda state: state.get("pickup") is not None)

        await room.local_participant.send_text(
            "Tôi chọn Bưu điện Hà Nội làm điểm đến.",
            topic="lk.chat",
        )
        await wait_for_booking_state(
            lambda state: state.get("destination") is not None
            and state.get("quote") is not None
            and state.get("confirmation_status") == "awaiting",
        )

        await room.local_participant.send_text(
            "Tôi xác nhận đặt chuyến này.",
            topic="lk.chat",
        )
        completed = await wait_for_booking_state(lambda state: state.get("booking") is not None)
        if not str(dict(completed["booking"])["booking_id"]).startswith("demo_"):
            raise RuntimeError("unexpected demo booking id")
        print("LIVEKIT_BOOKING_HAPPY_PATH=PASS")
        await asyncio.wait_for(booking_result_audio.wait(), timeout=45)
        print("LIVEKIT_BOOKING_RESULT_AUDIO=PASS")

    try:
        await room.connect(details.server_url, details.participant_token)
        await asyncio.wait_for(agent_joined.wait(), timeout=30)
        print("LIVEKIT_AGENT_JOINED=PASS")
        await asyncio.wait_for(agent_audio.wait(), timeout=45)
        print("LIVEKIT_AGENT_AUDIO=PASS")
        await asyncio.wait_for(booking_state_received.wait(), timeout=15)
        print("LIVEKIT_BOOKING_STATE=PASS")
        if booking:
            await asyncio.wait_for(agent_speaking.wait(), timeout=45)
            await asyncio.wait_for(agent_listening.wait(), timeout=45)
            await run_booking_happy_path()
    finally:
        for task in audio_tasks:
            task.cancel()
        await room.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--booking", action="store_true", help="Run the real LLM booking happy path")
    args = parser.parse_args()
    asyncio.run(run_smoke(booking=args.booking))
