"""Safe recovery when streaming STT emits a partial segment but no final."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from livekit.agents import AgentSession

from src.voice_agent.session_data import AloSMSessionData

logger = logging.getLogger(__name__)

_REPROMPT = "Tôi chưa nhận được câu nói hoàn chỉnh. Bạn vui lòng nói lại chậm và rõ hơn nhé."


class STTFinalFallback:
    """Reprompt without committing an unsafe partial transcript as user input."""

    def __init__(
        self,
        session: AgentSession[AloSMSessionData],
        *,
        delay_seconds: float,
    ) -> None:
        self._session = session
        self._delay_seconds = delay_seconds
        self._turn_sequence = 0
        self._speech_ended = False
        self._latest_partial = ""
        self._final_received = False
        self._reprompted = False
        self._task: asyncio.Task[None] | None = None

    def register(self) -> None:
        self._session.on("user_state_changed", self._on_event)
        self._session.on("user_input_transcribed", self._on_event)
        self._session.on("close", self._on_event)

    def _on_event(self, event: Any) -> None:
        event_type = str(getattr(event, "type", ""))
        if event_type == "close":
            self._cancel()
            return

        if event_type == "user_state_changed":
            old_state = str(event.old_state)
            new_state = str(event.new_state)
            if new_state == "speaking" and old_state != "speaking":
                self._turn_sequence += 1
                self._speech_ended = False
                self._latest_partial = ""
                self._final_received = False
                self._reprompted = False
                self._cancel()
            elif old_state == "speaking" and new_state == "listening":
                self._speech_ended = True
                self._schedule_if_needed()
            return

        if event_type != "user_input_transcribed":
            return
        if event.is_final:
            self._final_received = True
            self._latest_partial = ""
            self._cancel()
            return
        partial = str(event.transcript or "").strip()
        if partial:
            self._latest_partial = partial
            self._schedule_if_needed()

    def _schedule_if_needed(self) -> None:
        if (
            not self._speech_ended
            or self._final_received
            or self._reprompted
            or not self._latest_partial
            or (self._task is not None and not self._task.done())
        ):
            return
        turn_sequence = self._turn_sequence
        self._task = asyncio.create_task(
            self._reprompt_after_delay(turn_sequence),
            name=f"stt-final-fallback-{turn_sequence}",
        )

    async def _reprompt_after_delay(self, turn_sequence: int) -> None:
        try:
            await asyncio.sleep(self._delay_seconds)
            if (
                turn_sequence != self._turn_sequence
                or self._final_received
                or self._reprompted
                or not self._speech_ended
                or not self._latest_partial
            ):
                return
            self._reprompted = True
            logger.warning(
                "LiveKit STT final missing; issuing safe reprompt call_id=%s turn=%d "
                "partial_length=%d wait_seconds=%.2f",
                self._session.userdata.call_id,
                turn_sequence,
                len(self._latest_partial),
                self._delay_seconds,
            )
            self._session.say(_REPROMPT, allow_interruptions=True)
        except asyncio.CancelledError:
            raise
        except RuntimeError:
            logger.debug("skipping STT final fallback after session close")
        finally:
            if self._task is asyncio.current_task():
                self._task = None

    def _cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def aclose(self) -> None:
        task = self._task
        self._cancel()
        if task is not None:
            with suppress(asyncio.CancelledError):
                await task
