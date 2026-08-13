from __future__ import annotations

import base64
import io
from typing import Literal

import httpx
from openai import AsyncOpenAI

from src.config import Settings, get_settings


VoiceProviderName = Literal["openai", "gemini"]


class VoiceProviderError(RuntimeError):
    pass


def resolve_voice_provider(settings: Settings | None = None) -> VoiceProviderName:
    config = settings or get_settings()
    if config.voice_provider == "openai":
        if not config.openai_api_key:
            raise VoiceProviderError("OPENAI_API_KEY is required for voice_provider=openai")
        return "openai"
    if config.voice_provider == "gemini":
        if not config.google_api_key:
            raise VoiceProviderError("GEMINI_API_KEY is required for voice_provider=gemini")
        return "gemini"
    if config.openai_api_key:
        return "openai"
    if config.google_api_key:
        return "gemini"
    raise VoiceProviderError("Configure OPENAI_API_KEY or GEMINI_API_KEY for voice")


class OpenAIVoiceClient:
    def __init__(self, settings: Settings | None = None) -> None:
        config = settings or get_settings()
        if not config.openai_api_key:
            raise VoiceProviderError("OPENAI_API_KEY is required")
        self.settings = config
        self.client = AsyncOpenAI(api_key=config.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str) -> str:
        del mime_type
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"
        response = await self.client.audio.transcriptions.create(
            model=self.settings.voice_stt_model,
            file=audio_file,
            language="vi",
        )
        text = response.text.strip()
        if not text:
            raise VoiceProviderError("Không nhận diện được giọng nói")
        return text

    async def synthesize(self, text: str) -> bytes:
        cleaned = text.strip()
        if not cleaned:
            raise VoiceProviderError("Không có nội dung để đọc")
        response = await self.client.audio.speech.create(
            model=self.settings.voice_tts_model,
            voice=self.settings.voice_tts_voice,
            input=cleaned,
            response_format="mp3",
        )
        return response.content


class GeminiVoiceClient:
    def __init__(self, settings: Settings | None = None) -> None:
        config = settings or get_settings()
        if not config.google_api_key:
            raise VoiceProviderError("GEMINI_API_KEY is required")
        self.settings = config
        self.api_key = config.google_api_key

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str) -> str:
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type or "audio/webm",
                                "data": base64.b64encode(audio_bytes).decode("ascii"),
                            }
                        },
                        {
                            "text": (
                                "Transcribe this Vietnamese speech to plain text. "
                                "Return only the transcript without commentary."
                            )
                        },
                    ]
                }
            ]
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.voice_gemini_model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=self.settings.voice_timeout_seconds) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            body = response.json()

        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceProviderError("Gemini transcription returned no text") from exc
        if not text:
            raise VoiceProviderError("Không nhận diện được giọng nói")
        return text

    async def synthesize(self, text: str) -> bytes:
        del text
        raise VoiceProviderError("Gemini TTS is not enabled in this prototype")


def build_voice_client(settings: Settings | None = None) -> OpenAIVoiceClient | GeminiVoiceClient:
    provider = resolve_voice_provider(settings)
    if provider == "openai":
        return OpenAIVoiceClient(settings)
    return GeminiVoiceClient(settings)
