"""Custom LiveKit STT adapter that connects to the Zipformer ASR WebSocket server.

Replaces the OpenAI/Groq STT provider with local Zipformer streaming ASR.
Each AgentSession gets one WebSocket connection to asr_server.

Usage in server.py:
    from src.voice_agent.custom_stt import ZipformerSTT
    stt=ZipformerSTT(url=settings.zipformer_ws_url)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterable

import numpy as np

try:
    from livekit.agents import stt as lk_stt
    from livekit.agents.types import NOT_GIVEN
    from livekit import rtc
    _LIVEKIT_AVAILABLE = True
except ImportError:
    _LIVEKIT_AVAILABLE = False

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_CHANNELS = 1


class ZipformerSTT:
    """LiveKit-compatible STT that streams to the local Zipformer ASR server.

    Implements the livekit.agents.stt.STT interface via duck typing.
    """

    def __init__(
        self,
        *,
        url: str = "ws://localhost:9000/v1/stt",
        language: str = "vi",
        connect_timeout: float = 5.0,
        receive_timeout: float = 30.0,
    ) -> None:
        self._url = url
        self._language = language
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout

    # LiveKit calls stream() to get a STTStream
    def stream(self, *, language: str | None = None) -> "ZipformerSTTStream":
        return ZipformerSTTStream(
            url=self._url,
            language=language or self._language,
            connect_timeout=self._connect_timeout,
            receive_timeout=self._receive_timeout,
        )


class ZipformerSTTStream:
    """Per-utterance streaming interface — feeds AudioFrames, yields SpeechEvents."""

    def __init__(
        self,
        *,
        url: str,
        language: str,
        connect_timeout: float,
        receive_timeout: float,
    ) -> None:
        self._url = url
        self._language = language
        self._connect_timeout = connect_timeout
        self._receive_timeout = receive_timeout
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=256)
        self._closed = False

    def push_frame(self, frame) -> None:
        """Called by LiveKit with each AudioFrame."""
        if self._closed:
            return
        try:
            # Convert to PCM16 bytes
            pcm = _audio_frame_to_pcm16(frame)
            self._audio_queue.put_nowait(pcm)
        except asyncio.QueueFull:
            logger.warning("ZipformerSTT audio queue full — dropping frame")

    def end_input(self) -> None:
        """Signal end of audio input."""
        self._closed = True
        try:
            self._audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def aclose(self) -> None:
        self.end_input()

    async def __aiter__(self):
        """Async iterator that yields SpeechEvent-compatible dicts."""
        import websockets

        try:
            async with websockets.connect(
                self._url,
                open_timeout=self._connect_timeout,
            ) as ws:
                # Send start handshake
                await ws.send(json.dumps({
                    "type": "start",
                    "sample_rate": _SAMPLE_RATE,
                    "channels": _CHANNELS,
                    "language": self._language,
                }))

                # Sender task: reads from audio_queue, sends binary frames
                async def sender():
                    while True:
                        chunk = await self._audio_queue.get()
                        if chunk is None:
                            await ws.send(json.dumps({"type": "finish"}))
                            return
                        await ws.send(chunk)

                sender_task = asyncio.create_task(sender())
                t_speech_start: float | None = None

                try:
                    async for raw_msg in ws:
                        if isinstance(raw_msg, bytes):
                            continue
                        try:
                            msg = json.loads(raw_msg)
                        except json.JSONDecodeError:
                            continue

                        mtype = msg.get("type")
                        text = msg.get("text", "")

                        if mtype == "interim" and text:
                            if t_speech_start is None:
                                t_speech_start = time.perf_counter()
                                yield _make_speech_event("START_OF_SPEECH")
                            yield _make_speech_event("INTERIM_TRANSCRIPT", text=text, is_final=False)

                        elif mtype == "final" and text:
                            if t_speech_start is None:
                                t_speech_start = time.perf_counter()
                                yield _make_speech_event("START_OF_SPEECH")
                            yield _make_speech_event("FINAL_TRANSCRIPT", text=text, is_final=True)
                            yield _make_speech_event("END_OF_SPEECH")
                            t_speech_start = None

                        elif mtype in ("closed", "error"):
                            break

                finally:
                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass

        except Exception as exc:
            logger.error("ZipformerSTT WebSocket error: %s", exc)
            yield _make_speech_event("END_OF_SPEECH")


def _audio_frame_to_pcm16(frame) -> bytes:
    """Convert LiveKit AudioFrame to PCM16 LE bytes, resampling if needed."""
    try:
        # frame.data is bytes of int16 samples
        data = bytes(frame.data) if not isinstance(frame.data, bytes) else frame.data
        if frame.sample_rate != _SAMPLE_RATE:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            ratio = _SAMPLE_RATE / frame.sample_rate
            new_len = max(1, int(len(samples) * ratio))
            idx = np.linspace(0, len(samples) - 1, new_len)
            resampled = np.interp(idx, np.arange(len(samples)), samples)
            data = (resampled * 32767).astype(np.int16).tobytes()
        # Downmix to mono if stereo
        if frame.num_channels > 1:
            samples = np.frombuffer(data, dtype=np.int16)
            samples = samples.reshape(-1, frame.num_channels).mean(axis=1).astype(np.int16)
            data = samples.tobytes()
        return data
    except Exception as exc:
        logger.warning("audio_frame_to_pcm16 failed: %s", exc)
        return b""


def _make_speech_event(event_type: str, *, text: str = "", is_final: bool = False) -> dict:
    """Create a minimal speech event dict compatible with LiveKit STT interface."""
    return {
        "type": event_type,
        "text": text,
        "is_final": is_final,
        "timestamp": time.perf_counter(),
    }
