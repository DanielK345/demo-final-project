"""Publish typed booking state over LiveKit's native reliable data channel."""

from __future__ import annotations

import json
import logging

from livekit.agents import AgentSession

from src.voice_agent.session_data import AloSMSessionData

BOOKING_STATE_TOPIC = "alosm.booking_state.v1"
logger = logging.getLogger(__name__)


async def publish_booking_state(session: AgentSession[AloSMSessionData]) -> None:
    payload = json.dumps(
        session.userdata.public_state(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    try:
        await session.room_io.room.local_participant.publish_data(
            payload,
            reliable=True,
            topic=BOOKING_STATE_TOPIC,
        )
    except Exception:
        # The call can continue if a browser disconnects while a tool is completing.
        logger.exception("failed to publish LiveKit booking state")
