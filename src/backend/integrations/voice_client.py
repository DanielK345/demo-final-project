from __future__ import annotations

import base64
import io
import logging
from typing import Literal

import httpx
from openai import AsyncOpenAI, OpenAIError

from src.backend.config import Settings, get_settings
from src.voice.schemas import TTSResult

logger = logging.getLogger("uvicorn.error")

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
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transcription_model: str | None = None,
    ) -> None:
        config = settings or get_settings()
        if not config.openai_api_key:
            raise VoiceProviderError("OPENAI_API_KEY is required")
        self.settings = config
        self.transcription_model = transcription_model or config.voice_stt_model
        self.client = AsyncOpenAI(api_key=config.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, *, mime_type: str, prompt_hint: str = "") -> str:
        del mime_type
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"
        try:
            response = await self.client.audio.transcriptions.create(
                model=self.transcription_model,
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


async def synthesize_with_openai_tts(
    text: str,
    settings: Settings | None = None,
) -> TTSResult:
    """Last server-side TTS fallback after Edge voices are unavailable.

    This deliberately uses the OpenAI speech endpoint, not Whisper: Whisper is
    speech-to-text and cannot generate the agent's spoken response.
    """
    config = settings or get_settings()
    if not config.openai_api_key:
        raise VoiceProviderError("OPENAI_API_KEY is required for OpenAI TTS fallback")

    client = AsyncOpenAI(api_key=config.openai_api_key, max_retries=0)
    try:
        response = await client.audio.speech.create(
            model=config.voice_tts_model,
            voice=config.openai_tts_voice,
            input=text,
            response_format="mp3",
            timeout=config.voice_timeout_seconds,
        )
        audio = await response.aread()
    except OpenAIError as exc:
        raise VoiceProviderError("OpenAI TTS fallback failed") from exc
    if not audio:
        raise VoiceProviderError("OpenAI TTS fallback returned empty audio")

    logger.info(
        "OpenAI TTS fallback succeeded model=%s voice=%s",
        config.voice_tts_model,
        config.openai_tts_voice,
    )
    return TTSResult(
        audio=audio,
        mime_type="audio/mpeg",
        text=text,
        provider="openai",
        voice=config.openai_tts_voice,
        fallback_used=True,
    )


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
        try:
            async with httpx.AsyncClient(timeout=self.settings.voice_timeout_seconds) as client:
                response = await client.post(url, params={"key": self.api_key}, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise VoiceProviderError("Gemini transcription failed") from exc

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
