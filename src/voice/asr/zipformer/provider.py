from __future__ import annotations

from src.voice.asr.zipformer.service import ZipformerASRService, get_zipformer_service
from src.voice.schemas import ASRResult


class ZipformerASRProvider:
    def __init__(self, service: ZipformerASRService | None = None) -> None:
        self.service = service or get_zipformer_service()

    async def transcribe(
        self,
        pcm16_audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "vi",
        prompt_hint: str = "",
    ) -> ASRResult:
        del prompt_hint
        result = await self.service.transcribe_pcm16(pcm16_audio, sample_rate=sample_rate)
        return ASRResult(
            text=result.text,
            confidence=result.confidence if result.confidence is not None else 0.0,
            language=language,
            duration_ms=result.audio_duration_ms,
            raw={
                "provider": "zipformer",
                "inference_ms": result.inference_ms,
                "queue_wait_ms": result.queue_wait_ms,
                "realtime_factor": result.realtime_factor,
            },
        )
