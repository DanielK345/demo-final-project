from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from src.voice.text.rewrite_contract import TranscriptRewriteResult
from src.voice_agent.session_data import AloSMSessionData
from src.voice_agent.state_sync import (
    BOOKING_STATE_TOPIC,
    TRANSCRIPT_REWRITE_TOPIC,
    publish_booking_state,
    publish_transcript_rewrite,
)


def _userdata() -> AloSMSessionData:
    return AloSMSessionData(
        app_session_id="session-livekit",
        call_id="call-livekit",
        user_id="user-livekit",
        participant_identity="participant-livekit",
    )


class _DisconnectedRoom:
    def isconnected(self) -> bool:
        return False

    @property
    def local_participant(self) -> Any:
        raise AssertionError("local_participant must not be accessed before connection")


class _LocalParticipant:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, str]] = []

    async def publish_data(self, payload: str, *, reliable: bool, topic: str) -> None:
        self.calls.append((payload, reliable, topic))


class _ConnectedRoom:
    def __init__(self) -> None:
        self.local_participant = _LocalParticipant()

    def isconnected(self) -> bool:
        return True


def _session(room: object) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            userdata=_userdata(),
            room_io=SimpleNamespace(room=room),
        ),
    )


@pytest.mark.asyncio
async def test_publish_booking_state_skips_before_room_connection() -> None:
    assert await publish_booking_state(_session(_DisconnectedRoom())) is False


@pytest.mark.asyncio
async def test_publish_booking_state_uses_reliable_topic_after_connection() -> None:
    room = _ConnectedRoom()

    assert await publish_booking_state(_session(room)) is True
    assert len(room.local_participant.calls) == 1
    payload, reliable, topic = room.local_participant.calls[0]
    assert '"confirmation_status":"not_requested"' in payload
    assert reliable is True
    assert topic == BOOKING_STATE_TOPIC


@pytest.mark.asyncio
async def test_publish_transcript_rewrite_includes_item_and_latency() -> None:
    room = _ConnectedRoom()
    result = TranscriptRewriteResult(
        raw_text="ALO TOI MUON DAT XE",
        normalized_text="Alo, tôi muốn đặt xe.",
        applied=True,
        reason="applied",
        duration_ms=418,
    )

    assert await publish_transcript_rewrite(_session(room), "item-user-1", result) is True
    payload, reliable, topic = room.local_participant.calls[0]
    assert '"item_id":"item-user-1"' in payload
    assert '"normalized_text":"Alo, tôi muốn đặt xe."' in payload
    assert '"duration_ms":418' in payload
    assert reliable is True
    assert topic == TRANSCRIPT_REWRITE_TOPIC
