"""OpenAI TTS provider for production-grade reliability."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openai import AsyncOpenAI, OpenAIError

from src.voice.schemas import TTSResult
from src.voice.tts.errors import TTSError, TTSErrorCode

if TYPE_CHECKING:
    from src.backend.config import Settings

logger = logging.getLogger(__name__)

_MP3_SAMPLE_RATE = 24000


class OpenAITTSProvider:
    """Official OpenAI TTS Provider."""

    def __init__(self, settings: Settings, *, default_voice: str = "nova") -> None:
        self.settings = settings
        self.default_voice = default_voice
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def synthesize(self, text: str, *, voice: str | None = None) -> TTSResult:
        if not text.strip():
            return TTSResult(audio=b"", text=text)

        target_voice = voice or self.default_voice
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=target_voice,
                input=text,
                response_format="mp3",
                timeout=15.0,
            )
            audio_bytes = await response.aread()
        except OpenAIError as exc:
            logger.warning("OpenAI TTS synthesis failed: %s", exc)
            raise TTSError(TTSErrorCode.UNAVAILABLE, f"OpenAI TTS failed: {exc}") from exc

        return TTSResult(
            audio=audio_bytes,
            mime_type="audio/mpeg",
            sample_rate=_MP3_SAMPLE_RATE,
            text=text,
        )
