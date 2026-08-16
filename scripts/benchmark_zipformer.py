"""Actual CPU benchmark for the pinned ZipFormer model; never emits fake metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.voice.asr.zipformer.config import get_zipformer_settings  # noqa: E402
from src.voice.asr.zipformer.service import get_zipformer_service  # noqa: E402

DURATIONS = (1, 3, 5, 10, 30, 60)
CONCURRENCY_LEVELS = (1, 2, 4, 8)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return ordered[index]


def load_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("benchmark fixture must be mono PCM16 WAV")
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2"), wav.getframerate()


def duration_audio(source: np.ndarray, sample_rate: int, seconds: int) -> bytes:
    needed = sample_rate * seconds
    repeats = (needed + source.size - 1) // source.size
    return np.tile(source, repeats)[:needed].astype("<i2", copy=False).tobytes()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/voice-ai/zipformer-benchmark.json"))
    args = parser.parse_args()
    settings = get_zipformer_settings()
    fixtures = sorted((settings.asr_model_dir / "test_wavs").glob("*.wav"))
    if not fixtures:
        print("Pinned real WAV fixture is missing", file=sys.stderr)
        return 1
    source, sample_rate = load_pcm16(fixtures[0])
    if sample_rate != settings.asr_sample_rate:
        print(f"Expected {settings.asr_sample_rate} Hz benchmark WAV, got {sample_rate}", file=sys.stderr)
        return 1
    service = get_zipformer_service()
    await service.start()
    if not service.ready:
        print(f"ASR is not ready: {service.runtime.failure_reason}", file=sys.stderr)
        return 1
    rows: list[dict[str, float | int]] = []
    process = psutil.Process()
    try:
        for seconds in DURATIONS:
            audio = duration_audio(source, sample_rate, seconds)
            for concurrency in CONCURRENCY_LEVELS:
                cpu_before = process.cpu_times()
                rss_before = process.memory_info().rss
                started = time.perf_counter()

                async def one() -> tuple[float, float, float]:
                    request_started = time.perf_counter()
                    result = await service.transcribe_pcm16(audio, sample_rate=sample_rate)
                    return (
                        (time.perf_counter() - request_started) * 1000,
                        float(result.realtime_factor),
                        float(result.queue_wait_ms),
                    )

                results = await asyncio.gather(*(one() for _ in range(concurrency)))
                elapsed = time.perf_counter() - started
                cpu_after = process.cpu_times()
                cpu_seconds = (cpu_after.user + cpu_after.system) - (cpu_before.user + cpu_before.system)
                rss_after = process.memory_info().rss
                latencies = [item[0] for item in results]
                rtfs = [item[1] for item in results]
                waits = [item[2] for item in results]
                rows.append(
                    {
                        "audio_seconds": seconds,
                        "concurrency": concurrency,
                        "p50_ms": round(percentile(latencies, 0.50), 2),
                        "p95_ms": round(percentile(latencies, 0.95), 2),
                        "p99_ms": round(percentile(latencies, 0.99), 2),
                        "mean_rtf": round(statistics.fmean(rtfs), 4),
                        "mean_queue_wait_ms": round(statistics.fmean(waits), 2),
                        "throughput_requests_per_second": round(concurrency / elapsed, 3),
                        "error_rate": 0.0,
                        "process_cpu_percent_one_core": round(cpu_seconds / elapsed * 100, 2),
                        "process_rss_before_mb": round(rss_before / 1024 / 1024, 2),
                        "process_rss_after_mb": round(rss_after / 1024 / 1024, 2),
                    }
                )
    finally:
        await service.stop()
    report = {
        "generated_at_epoch": int(time.time()),
        "model": settings.asr_model_id,
        "artifact": settings.asr_model_dir.name,
        "runtime": "sherpa-onnx 1.13.4 CPU",
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "total_ram_mb": round(psutil.virtual_memory().total / 1024 / 1024, 2),
        },
        "method": "Real model inference using repeated/sliced PCM from the pinned Vietnamese WAV fixture; process CPU is normalized to one logical core and RSS is sampled immediately before/after each batch.",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} real benchmark rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
