from __future__ import annotations

import base64
import io
from typing import Literal

import httpx
from openai import AsyncOpenAI, OpenAIError

from src.backend.config import Settings, get_settings

VoiceProviderName = Literal["openai", "gemini", "zipformer"]


class VoiceProviderError(RuntimeError):
    pass


class NoSpeechDetectedError(VoiceProviderError):
    """ASR completed successfully but no usable speech was detected."""


def resolve_voice_provider(settings: Settings | None = None) -> VoiceProviderName:
    config = settings or get_settings()
    from src.voice.asr.zipformer.service import get_zipformer_service

    if config.voice_provider == "zipformer":
        if not get_zipformer_service().ready:
            raise VoiceProviderError("ZipFormer ASR model is not ready")
        return "zipformer"
    if config.voice_provider == "openai":
        if not config.openai_api_key:
            raise VoiceProviderError("OPENAI_API_KEY is required for voice_provider=openai")
        return "openai"
    if config.voice_provider == "gemini":
        if not config.google_api_key:
            raise VoiceProviderError("GEMINI_API_KEY is required for voice_provider=gemini")
        return "gemini"
    if get_zipformer_service().ready:
        return "zipformer"
    if config.openai_api_key:
        return "openai"
    if config.google_api_key:
        return "gemini"
    raise VoiceProviderError("Configure OPENAI_API_KEY or GEMINI_API_KEY for voice")


async def _synthesize_with_unified_tts(text: str) -> bytes:
    from src.voice.tts.errors import TTSError
    from src.voice.tts.orchestrator import get_tts_orchestrator

    try:
        result = await get_tts_orchestrator().synthesize(text)
    except TTSError as exc:
        raise VoiceProviderError(str(exc)) from exc
    return result.audio


class OpenAIVoiceClient:
    def __init__(self, settings: Settings | None = None) -> None:
        config = settings or get_settings()
        if not config.openai_api_key:
            raise VoiceProviderError("OPENAI_API_KEY is required")
        self.settings = config
        self.client = AsyncOpenAI(api_key=config.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str, prompt_hint: str = "") -> str:
        del mime_type
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"
        try:
            response = await self.client.audio.transcriptions.create(
                model=self.settings.voice_stt_model,
                file=audio_file,
                language="vi",
                prompt=prompt_hint or None,
                timeout=self.settings.voice_timeout_seconds,
            )
        except OpenAIError as exc:
            raise VoiceProviderError("OpenAI transcription failed") from exc
        text = response.text.strip()
        if not text:
            raise NoSpeechDetectedError("Không nhận diện được giọng nói")
        return text

    async def synthesize(self, text: str) -> bytes:
        return await _synthesize_with_unified_tts(text)


class GeminiVoiceClient:
    def __init__(self, settings: Settings | None = None) -> None:
        config = settings or get_settings()
        if not config.google_api_key:
            raise VoiceProviderError("GEMINI_API_KEY is required")
        self.settings = config
        self.api_key = config.google_api_key

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str, prompt_hint: str = "") -> str:
        instruction = (
            "Transcribe this Vietnamese ride-hailing speech verbatim to plain text. "
            "Preserve numbers, negation, confirmation, addresses, and uncertainty. "
            "Return only the transcript without commentary."
        )
        if prompt_hint:
            instruction += f" Expected terminology: {prompt_hint}"
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
                        {"text": instruction},
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
            raise NoSpeechDetectedError("Không nhận diện được giọng nói")
        return text

    async def synthesize(self, text: str) -> bytes:
        return await _synthesize_with_unified_tts(text)


class ZipformerVoiceClient:
    async def transcribe(self, audio_bytes: bytes, *, mime_type: str, prompt_hint: str = "") -> str:
        del prompt_hint
        from src.voice.asr.zipformer.service import get_zipformer_service

        suffix = {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp4": "m4a",
            "audio/ogg": "ogg",
        }.get(mime_type.partition(";")[0].lower(), "webm")
        try:
            result = await get_zipformer_service().transcribe_upload(
                audio_bytes,
                filename=f"recording.{suffix}",
                mime_type=mime_type,
            )
        except Exception as exc:
            raise VoiceProviderError("ZipFormer transcription failed") from exc
        if not result.text:
            raise NoSpeechDetectedError("Không nhận diện được giọng nói")
        return result.text

    async def synthesize(self, text: str) -> bytes:
        return await _synthesize_with_unified_tts(text)


def build_voice_client(
    settings: Settings | None = None,
) -> OpenAIVoiceClient | GeminiVoiceClient | ZipformerVoiceClient:
    provider = resolve_voice_provider(settings)
    if provider == "openai":
        return OpenAIVoiceClient(settings)
    if provider == "zipformer":
        return ZipformerVoiceClient()
    return GeminiVoiceClient(settings)
