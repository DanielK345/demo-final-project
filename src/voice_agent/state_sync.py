"""Publish typed booking state over LiveKit's native reliable data channel."""

from __future__ import annotations

import asyncio
import json
import logging

from livekit.agents import AgentSession

from src.voice.text.rewrite_contract import TranscriptRewriteResult
from src.voice_agent.session_data import AloSMSessionData

BOOKING_STATE_TOPIC = "alosm.booking_state.v1"
TRANSCRIPT_REWRITE_TOPIC = "alosm.transcript_rewrite.v1"
DATA_PUBLISH_TIMEOUT_SECONDS = 1.0
logger = logging.getLogger(__name__)


async def publish_booking_state(session: AgentSession[AloSMSessionData]) -> bool:
    room = session.room_io.room
    if not room.isconnected():
        # Provider errors may fire while AgentSession.start() is still creating
        # RoomIO. The state is already persisted by the caller and the session
        # publishes the latest snapshot once start() completes.
        logger.debug("skipping LiveKit booking state publish before room connection")
        return False

    payload = json.dumps(
        session.userdata.public_state(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    try:
        async with asyncio.timeout(DATA_PUBLISH_TIMEOUT_SECONDS):
            await session.room_io.room.local_participant.publish_data(
                payload,
                reliable=True,
                topic=BOOKING_STATE_TOPIC,
            )
        return True
    except TimeoutError:
        logger.warning("LiveKit booking state publish timed out")
        return False
    except Exception:
        # A disconnect can race the check above while a tool is completing. It
        # is an expected lifecycle event, not a publication defect.
        if not room.isconnected():
            logger.debug("skipping LiveKit booking state publish after room disconnect")
            return False
        logger.exception("failed to publish LiveKit booking state")
        return False


async def publish_transcript_rewrite(
    session: AgentSession[AloSMSessionData],
    item_id: str,
    result: TranscriptRewriteResult,
) -> bool:
    """Publish the final rewrite for the matching realtime ASR bubble."""

    room = session.room_io.room
    if not room.isconnected():
        logger.debug("skipping transcript rewrite publish after room disconnect")
        return False
    payload = json.dumps(
        {
            "schema_version": "1",
            "item_id": item_id,
            "raw_text": result.raw_text,
            "normalized_text": result.normalized_text,
            "applied": result.applied,
            "status": result.reason,
            "duration_ms": result.duration_ms,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    try:
        async with asyncio.timeout(DATA_PUBLISH_TIMEOUT_SECONDS):
            await room.local_participant.publish_data(
                payload,
                reliable=True,
                topic=TRANSCRIPT_REWRITE_TOPIC,
            )
        return True
    except TimeoutError:
        logger.warning(
            "LiveKit transcript rewrite publish timed out item_id=%s",
            item_id,
        )
        return False
    except Exception:
        if not room.isconnected():
            logger.debug("skipping transcript rewrite publish during room disconnect")
            return False
        logger.exception("failed to publish LiveKit transcript rewrite")
        return False
