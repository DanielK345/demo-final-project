"""Explicit unavailable ASR provider used when production credentials are absent."""

from src.voice.schemas import ASRResult


class UnavailableASRProvider:
    async def transcribe(
        self,
        pcm16_audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "vi",
        prompt_hint: str = "",
    ) -> ASRResult:
        del pcm16_audio, sample_rate, language, prompt_hint
        raise RuntimeError("GROQ_API_KEY is required for the WebSocket voice ASR pipeline")
