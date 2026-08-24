from __future__ import annotations

import asyncio
from collections import defaultdict
from types import SimpleNamespace
from typing import Any

import pytest

from src.voice_agent.session_data import AloSMSessionData
from src.voice_agent.stt_final_fallback import STTFinalFallback


class _Session:
    def __init__(self) -> None:
        self.userdata = AloSMSessionData(
            app_session_id="session",
            call_id="call",
            user_id="user",
            participant_identity="participant",
        )
        self.callbacks: dict[str, list[Any]] = defaultdict(list)
        self.said: list[tuple[str, bool]] = []

    def on(self, event_name: str, callback: Any) -> None:
        self.callbacks[event_name].append(callback)

    def emit(self, event_name: str, **fields: object) -> None:
        event = SimpleNamespace(type=event_name, **fields)
        for callback in self.callbacks[event_name]:
            callback(event)

    def say(self, text: str, *, allow_interruptions: bool) -> None:
        self.said.append((text, allow_interruptions))


@pytest.mark.asyncio
async def test_missing_final_after_partial_triggers_safe_reprompt() -> None:
    session = _Session()
    fallback = STTFinalFallback(session, delay_seconds=0.01)  # type: ignore[arg-type]
    fallback.register()

    session.emit("user_state_changed", old_state="listening", new_state="speaking")
    session.emit("user_input_transcribed", transcript="cổng chính", is_final=False)
    session.emit("user_state_changed", old_state="speaking", new_state="listening")
    await asyncio.sleep(0.03)

    assert len(session.said) == 1
    assert "nói lại" in session.said[0][0]
    assert session.said[0][1] is True
    await fallback.aclose()


@pytest.mark.asyncio
async def test_final_transcript_cancels_pending_reprompt() -> None:
    session = _Session()
    fallback = STTFinalFallback(session, delay_seconds=0.02)  # type: ignore[arg-type]
    fallback.register()

    session.emit("user_state_changed", old_state="listening", new_state="speaking")
    session.emit("user_input_transcribed", transcript="cổng chính", is_final=False)
    session.emit("user_state_changed", old_state="speaking", new_state="listening")
    session.emit("user_input_transcribed", transcript="cổng chính VinUni", is_final=True)
    await asyncio.sleep(0.04)

    assert session.said == []
    await fallback.aclose()


@pytest.mark.asyncio
async def test_new_speech_turn_cancels_previous_partial_fallback() -> None:
    session = _Session()
    fallback = STTFinalFallback(session, delay_seconds=0.02)  # type: ignore[arg-type]
    fallback.register()

    session.emit("user_state_changed", old_state="listening", new_state="speaking")
    session.emit("user_input_transcribed", transcript="cổng", is_final=False)
    session.emit("user_state_changed", old_state="speaking", new_state="listening")
    session.emit("user_state_changed", old_state="listening", new_state="speaking")
    await asyncio.sleep(0.04)

    assert session.said == []
    await fallback.aclose()


@pytest.mark.asyncio
async def test_late_partial_does_not_repeat_reprompt_for_same_turn() -> None:
    session = _Session()
    fallback = STTFinalFallback(session, delay_seconds=0.01)  # type: ignore[arg-type]
    fallback.register()

    session.emit("user_state_changed", old_state="listening", new_state="speaking")
    session.emit("user_input_transcribed", transcript="cổng", is_final=False)
    session.emit("user_state_changed", old_state="speaking", new_state="listening")
    await asyncio.sleep(0.03)
    session.emit("user_input_transcribed", transcript="cổng chính", is_final=False)
    await asyncio.sleep(0.03)

    assert len(session.said) == 1
    await fallback.aclose()
