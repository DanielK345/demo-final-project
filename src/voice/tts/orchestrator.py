from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache

from src.voice.config import VoiceSettings, get_voice_settings
from src.voice.schemas import TTSResult
from src.voice.tts.audio_validator import TTSAudioValidator
from src.voice.tts.edge_tts_provider import EdgeTTSProvider
from src.voice.tts.errors import TTSError, TTSErrorCode
from src.voice.tts.formatter import format_for_speech, sanitize_for_speech
from src.voice.tts.metrics import TTSMetrics
from src.voice.tts.output_review import DeterministicTTSOutputReviewer, OutputDecision
from src.voice.tts.pronunciation import apply_pronunciation_overrides

logger = logging.getLogger(__name__)


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float | None = None


@dataclass
class _CacheEntry:
    result: TTSResult
    expires_at: float


class TTSOrchestrator:
    def __init__(self, settings: VoiceSettings | None = None) -> None:
        self.settings = settings or get_voice_settings()
        self.provider = EdgeTTSProvider(rate=self.settings.voice_tts_rate)
        self.reviewer = DeterministicTTSOutputReviewer(max_chars=self.settings.voice_tts_max_text_chars)
        self.validator = TTSAudioValidator(
            ffmpeg_path=self.settings.voice_tts_ffmpeg_path,
            ffprobe_path=self.settings.voice_tts_ffprobe_path,
            max_audio_bytes=self.settings.voice_tts_max_audio_bytes,
        )
        self.metrics = TTSMetrics()
        self._semaphore = asyncio.Semaphore(self.settings.voice_tts_max_concurrency)
        self._pending_lock = asyncio.Lock()
        self._pending = 0
        self._circuits: dict[str, _Circuit] = {}
        self._cache: OrderedDict[tuple[str, str, float], _CacheEntry] = OrderedDict()
        self.active_voice: str | None = None
        self.degraded = False

    @property
    def voices(self) -> list[str]:
        configured = [self.settings.voice_tts_primary_voice, *self.settings.voice_tts_fallback_voice_list]
        return list(dict.fromkeys(voice for voice in configured if voice))

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        cacheable: bool = False,
        review_context: dict[str, object] | None = None,
    ) -> TTSResult:
        review = self.reviewer.review(text, context=review_context)
        if review.decision is OutputDecision.BLOCK:
            raise TTSError(TTSErrorCode.OUTPUT_BLOCKED, "TTS output was blocked", status_code=422)
        spoken_text = apply_pronunciation_overrides(review.approved_text)
        spoken_text = sanitize_for_speech(format_for_speech(spoken_text))
        voices = [voice] if voice else self.voices
        if not voices:
            raise TTSError(TTSErrorCode.UNAVAILABLE, "No TTS voice is configured")

        self.metrics.increment(requests_total=1)
        was_queued = False
        async with self._pending_lock:
            capacity = self.settings.voice_tts_max_concurrency + self.settings.voice_tts_queue_size
            if self._pending >= capacity:
                self.metrics.increment(errors_total=1, queue_rejected_total=1)
                raise TTSError(TTSErrorCode.QUEUE_FULL, "TTS queue is full", status_code=429)
            self._pending += 1
            was_queued = self._pending > self.settings.voice_tts_max_concurrency
            if was_queued:
                self.metrics.increment(queued_requests=1)
        try:
            async with self._semaphore:
                try:
                    async with asyncio.timeout(self.settings.voice_tts_request_deadline_seconds):
                        return await self._synthesize_with_fallback(
                            spoken_text,
                            original_text=text,
                            voices=voices,
                            review_decision=review.decision.value,
                            review_reasons=review.reason_codes,
                            cacheable=cacheable,
                        )
                except TimeoutError as exc:
                    self.metrics.increment(errors_total=1, timeout_total=1)
                    raise TTSError(TTSErrorCode.TIMEOUT, "TTS request deadline exceeded") from exc
        finally:
            async with self._pending_lock:
                if was_queued:
                    self.metrics.increment(queued_requests=-1)
                self._pending -= 1

    async def _synthesize_with_fallback(
        self,
        spoken_text: str,
        *,
        original_text: str,
        voices: list[str],
        review_decision: str,
        review_reasons: list[str],
        cacheable: bool,
    ) -> TTSResult:
        started = time.perf_counter()
        last_error: Exception | None = None
        self.metrics.increment(concurrent_requests=1)
        try:
            request_voices = [candidate for candidate in voices if not self._circuit_open(candidate)]
            for attempt in range(self.settings.voice_tts_max_attempts_per_voice):
                for index, candidate in enumerate(request_voices):
                    cached = self._cache_get(spoken_text, candidate)
                    if cached is not None:
                        self.metrics.increment(cache_hit_total=1, success_total=1)
                        return cached
                    try:
                        async with asyncio.timeout(self.settings.voice_tts_timeout_seconds):
                            raw = await self.provider.synthesize(spoken_text, voice=candidate)
                        validated = await asyncio.to_thread(
                            self.validator.validate,
                            raw.audio,
                            expected_mime=raw.mime_type,
                        )
                    except TimeoutError as exc:
                        last_error = exc
                        self.metrics.increment(timeout_total=1)
                        self._record_failure(candidate)
                        logger.warning("TTS attempt timed out voice=%s attempt=%s", candidate, attempt + 1)
                        continue
                    except Exception as exc:
                        last_error = exc
                        self.metrics.increment(validation_failure_total=1 if isinstance(exc, TTSError) else 0)
                        self._record_failure(candidate)
                        logger.warning(
                            "TTS attempt failed voice=%s attempt=%s error_type=%s",
                            candidate,
                            attempt + 1,
                            type(exc).__name__,
                        )
                        continue

                    self._record_success(candidate)
                    fallback_used = index > 0 or candidate != self.settings.voice_tts_primary_voice
                    if fallback_used:
                        self.metrics.increment(fallback_total=1)
                    elapsed = time.perf_counter() - started
                    result = TTSResult(
                        audio=raw.audio,
                        mime_type=raw.mime_type,
                        sample_rate=validated.sample_rate,
                        text=original_text,
                        duration_ms=validated.duration_ms,
                        provider="edge",
                        voice=candidate,
                        fallback_used=fallback_used,
                        review_decision=review_decision,
                        review_reason_codes=review_reasons,
                        spoken_text=spoken_text,
                        audio_metrics={
                            "codec": validated.codec,
                            "channels": validated.channels,
                            "rms": validated.rms,
                            "peak": validated.peak,
                            "silence_ratio": validated.silence_ratio,
                            "clipped_ratio": validated.clipped_ratio,
                        },
                    )
                    if cacheable:
                        self._cache_put(spoken_text, candidate, result)
                    self.active_voice = candidate
                    self.degraded = fallback_used
                    self.metrics.increment(
                        success_total=1,
                        synthesis_seconds_total=elapsed,
                        audio_seconds_total=validated.duration_ms / 1000,
                    )
                    return result
                if attempt + 1 < self.settings.voice_tts_max_attempts_per_voice:
                    await asyncio.sleep(0.2 * (2**attempt) + random.uniform(0, 0.1))
        finally:
            self.metrics.increment(concurrent_requests=-1)
        self.metrics.increment(errors_total=1)
        raise TTSError(TTSErrorCode.UNAVAILABLE, "All configured TTS voices failed") from last_error

    async def probe(self) -> bool:
        try:
            await self.synthesize("Xin chào, hệ thống giọng nói đã sẵn sàng.")
        except TTSError:
            return False
        return True

    async def prewarm(self, phrases: list[str]) -> None:
        for phrase in phrases:
            try:
                await self.synthesize(phrase, cacheable=True)
            except TTSError:
                logger.exception("TTS prewarm phrase failed")
                return

    def health(self) -> dict[str, object]:
        return {
            "status": "ready" if self.active_voice else "not_ready",
            "degraded": self.degraded,
            "active_voice": self.active_voice,
            "configured_voices": self.voices,
            "circuits": {
                voice: "open" if self._circuit_open(voice) else "closed" for voice in self.voices
            },
        }

    def _circuit_open(self, voice: str) -> bool:
        circuit = self._circuits.setdefault(voice, _Circuit())
        if circuit.opened_at is None:
            return False
        if time.monotonic() - circuit.opened_at >= self.settings.voice_tts_circuit_cooldown_seconds:
            circuit.failures = 0
            circuit.opened_at = None
            return False
        return True

    def _record_failure(self, voice: str) -> None:
        circuit = self._circuits.setdefault(voice, _Circuit())
        circuit.failures += 1
        if circuit.failures >= self.settings.voice_tts_circuit_failure_threshold:
            circuit.opened_at = time.monotonic()

    def _record_success(self, voice: str) -> None:
        self._circuits[voice] = _Circuit()

    def _cache_get(self, text: str, voice: str) -> TTSResult | None:
        key = (text, voice, self.settings.voice_tts_rate)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return entry.result.model_copy(deep=True)

    def _cache_put(self, text: str, voice: str, result: TTSResult) -> None:
        if len(text) > self.settings.voice_tts_cache_max_text_chars:
            return
        key = (text, voice, self.settings.voice_tts_rate)
        self._cache[key] = _CacheEntry(
            result=result.model_copy(deep=True),
            expires_at=time.monotonic() + self.settings.voice_tts_cache_ttl_seconds,
        )
        self._cache.move_to_end(key)
        while len(self._cache) > self.settings.voice_tts_cache_max_entries:
            self._cache.popitem(last=False)


@lru_cache
def get_tts_orchestrator() -> TTSOrchestrator:
    return TTSOrchestrator()
