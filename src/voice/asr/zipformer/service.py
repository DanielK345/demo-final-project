from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from src.voice.asr.zipformer.audio import DecodedAudio, decode_audio, pcm16_to_float32, validate_upload
from src.voice.asr.zipformer.config import ZipformerSettings, get_zipformer_settings
from src.voice.asr.zipformer.errors import ASRErrorCode, ZipformerASRError
from src.voice.asr.zipformer.metrics import ASRMetrics
from src.voice.asr.zipformer.runtime import RuntimeResult, ZipformerRuntime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceResult:
    text: str
    confidence: float | None
    audio_duration_ms: int
    queue_wait_ms: int
    preprocessing_ms: int
    inference_ms: int
    processing_ms: int
    realtime_factor: float


@dataclass
class _Job:
    samples: np.ndarray
    queued_at: float
    future: asyncio.Future[tuple[RuntimeResult, int]]


class ZipformerASRService:
    def __init__(self, settings: ZipformerSettings | None = None) -> None:
        self.settings = settings or get_zipformer_settings()
        self.runtime = ZipformerRuntime(self.settings)
        self.metrics = ASRMetrics()
        self._queue: asyncio.Queue[_Job | None] = asyncio.Queue(maxsize=self.settings.asr_queue_size)
        self._workers: list[asyncio.Task[None]] = []

    @property
    def ready(self) -> bool:
        return self.runtime.ready and bool(self._workers)

    async def start(self) -> None:
        if not self.settings.asr_enabled or self._workers:
            return
        try:
            await asyncio.to_thread(self.runtime.load_and_warm)
        except Exception:
            self.metrics.update(model_ready=0)
            if self.settings.asr_required:
                raise
            return
        self._queue = asyncio.Queue(maxsize=self.settings.asr_queue_size)
        self._workers = [
            asyncio.create_task(self._worker(index), name=f"zipformer-asr-{index}")
            for index in range(self.settings.asr_max_concurrency)
        ]
        self.metrics.update(model_ready=1)

    async def stop(self) -> None:
        workers, self._workers = self._workers, []
        for _ in workers:
            await self._queue.put(None)
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self.metrics.update(model_ready=0, concurrent_requests=0, queue_depth=0)

    async def transcribe_upload(self, data: bytes, *, filename: str, mime_type: str) -> ServiceResult:
        validate_upload(data, filename=filename, mime_type=mime_type, settings=self.settings)
        decoded = await asyncio.to_thread(decode_audio, data, settings=self.settings)
        return await self._submit(decoded)

    async def transcribe_pcm16(self, data: bytes, *, sample_rate: int) -> ServiceResult:
        if sample_rate != self.settings.asr_sample_rate:
            raise ZipformerASRError(
                ASRErrorCode.INVALID_AUDIO,
                f"PCM16 stream must use {self.settings.asr_sample_rate} Hz",
                status_code=422,
            )
        started = time.perf_counter()
        samples = pcm16_to_float32(data)
        duration_ms = round(samples.size / sample_rate * 1000)
        if duration_ms > self.settings.max_audio_duration_seconds * 1000:
            raise ZipformerASRError(ASRErrorCode.AUDIO_TOO_LONG, "Audio exceeds duration limit", status_code=413)
        decoded = DecodedAudio(
            samples=samples,
            duration_ms=duration_ms,
            preprocessing_ms=round((time.perf_counter() - started) * 1000),
        )
        return await self._submit(decoded)

    async def _submit(self, decoded: DecodedAudio) -> ServiceResult:
        if not self.ready:
            raise ZipformerASRError(ASRErrorCode.MODEL_UNAVAILABLE, "ASR model is not ready", status_code=503)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[tuple[RuntimeResult, int]] = loop.create_future()
        job = _Job(decoded.samples, time.perf_counter(), future)
        self.metrics.increment(requests_total=1)
        try:
            self._queue.put_nowait(job)
        except asyncio.QueueFull as exc:
            self.metrics.increment(errors_total=1, queue_rejected_total=1)
            raise ZipformerASRError(ASRErrorCode.QUEUE_FULL, "ASR queue is full", status_code=429) from exc
        self.metrics.update(queue_depth=self._queue.qsize())
        total_started = time.perf_counter()
        try:
            runtime_result, queue_wait_ms = await asyncio.wait_for(
                future,
                timeout=self.settings.asr_inference_timeout_seconds,
            )
        except TimeoutError as exc:
            self.metrics.increment(errors_total=1)
            raise ZipformerASRError(ASRErrorCode.INFERENCE_TIMEOUT, "ASR inference timed out", status_code=504) from exc
        processing_ms = round((time.perf_counter() - total_started) * 1000) + decoded.preprocessing_ms
        rtf = runtime_result.inference_ms / max(decoded.duration_ms, 1)
        self.metrics.increment(
            success_total=1,
            audio_seconds_total=decoded.duration_ms / 1000,
            queue_wait_seconds_total=queue_wait_ms / 1000,
            preprocessing_seconds_total=decoded.preprocessing_ms / 1000,
            inference_seconds_total=runtime_result.inference_ms / 1000,
            request_seconds_total=processing_ms / 1000,
            realtime_factor_sum=rtf,
        )
        return ServiceResult(
            text=runtime_result.text,
            confidence=runtime_result.confidence,
            audio_duration_ms=decoded.duration_ms,
            queue_wait_ms=queue_wait_ms,
            preprocessing_ms=decoded.preprocessing_ms,
            inference_ms=runtime_result.inference_ms,
            processing_ms=processing_ms,
            realtime_factor=round(rtf, 4),
        )

    async def _worker(self, index: int) -> None:
        del index
        while True:
            job = await self._queue.get()
            self.metrics.update(queue_depth=self._queue.qsize())
            if job is None:
                self._queue.task_done()
                return
            queue_wait_ms = round((time.perf_counter() - job.queued_at) * 1000)
            self.metrics.increment(concurrent_requests=1)
            try:
                result = await asyncio.to_thread(self.runtime.transcribe, job.samples)
                if not job.future.done():
                    job.future.set_result((result, queue_wait_ms))
            except Exception as exc:
                self.metrics.increment(errors_total=1)
                if not job.future.done():
                    job.future.set_exception(exc)
            finally:
                self.metrics.increment(concurrent_requests=-1)
                self._queue.task_done()


@lru_cache
def get_zipformer_service() -> ZipformerASRService:
    return ZipformerASRService()
