"""Real TTS -> audio validation -> ZipFormer review; never uses mocked providers."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.voice.asr.zipformer.audio import decode_audio  # noqa: E402
from src.voice.asr.zipformer.config import get_zipformer_settings  # noqa: E402
from src.voice.asr.zipformer.runtime import ZipformerRuntime  # noqa: E402
from src.voice.config import get_voice_settings  # noqa: E402
from src.voice.tts.audio_validator import TTSAudioValidator  # noqa: E402
from src.voice.tts.edge_tts_provider import EdgeTTSProvider  # noqa: E402
from src.voice.tts.orchestrator import TTSOrchestrator  # noqa: E402

CASES = (
    ("greeting", "Xin chào, tôi là trợ lý AloSM và sẵn sàng hỗ trợ bạn.", ("xin", "chào")),
    (
        "fare_time",
        "Giá dự kiến là 85.000 ₫, xe sẽ đến lúc 15:30.",
        ("giá", "giờ"),
    ),
    (
        "negation",
        "Chuyến xe chưa được xác nhận và tôi không tự động đặt xe khi bạn chưa đồng ý.",
        ("chưa", "không"),
    ),
    (
        "place",
        "Xe sẽ đón bạn tại Landmark 81 và đi đến Bến Thành.",
        ("đón", "bến"),
    ),
)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return " ".join("".join(char for char in decomposed if unicodedata.category(char) != "Mn").split())


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_item in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_item in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: str, hypothesis: str, *, characters: bool = False) -> float:
    normalized_reference = normalize(reference)
    normalized_hypothesis = normalize(hypothesis)
    reference_items = list(normalized_reference.replace(" ", "")) if characters else normalized_reference.split()
    hypothesis_items = list(normalized_hypothesis.replace(" ", "")) if characters else normalized_hypothesis.split()
    return edit_distance(reference_items, hypothesis_items) / max(len(reference_items), 1)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/voice-ai/tts-output-live-report.json"))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    voice_settings = get_voice_settings()
    asr_settings = get_zipformer_settings()
    runtime = ZipformerRuntime(asr_settings)
    await asyncio.to_thread(runtime.load_and_warm)
    validator = TTSAudioValidator(
        ffmpeg_path=voice_settings.voice_tts_ffmpeg_path,
        ffprobe_path=voice_settings.voice_tts_ffprobe_path,
        max_audio_bytes=voice_settings.voice_tts_max_audio_bytes,
    )
    provider = EdgeTTSProvider(rate=voice_settings.voice_tts_rate)

    voice_matrix: list[dict[str, object]] = []
    for voice in [voice_settings.voice_tts_primary_voice, *voice_settings.voice_tts_fallback_voice_list]:
        started = time.perf_counter()
        try:
            async with asyncio.timeout(voice_settings.voice_tts_timeout_seconds):
                raw = await provider.synthesize("Xin chào, kiểm tra giọng nói tiếng Việt.", voice=voice)
            validated = await asyncio.to_thread(validator.validate, raw.audio, expected_mime=raw.mime_type)
            voice_matrix.append(
                {
                    "voice": voice,
                    "healthy": True,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "audio_bytes": len(raw.audio),
                    "duration_ms": validated.duration_ms,
                    "rms": validated.rms,
                    "peak": validated.peak,
                }
            )
        except Exception as exc:
            voice_matrix.append(
                {
                    "voice": voice,
                    "healthy": False,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "error_type": type(exc).__name__,
                }
            )

    if not any(bool(row["healthy"]) for row in voice_matrix):
        print("No configured real TTS voice passed the technical gate", file=sys.stderr)
        return 1

    fallback_settings = voice_settings.model_copy(
        update={
            "voice_tts_primary_voice": "vi-VN-IntentionalUnavailableNeural",
            "voice_tts_fallback_voices": "vi-VN-NamMinhNeural",
            "voice_tts_timeout_seconds": 5.0,
            "voice_tts_request_deadline_seconds": 20.0,
            "voice_tts_max_attempts_per_voice": 1,
        }
    )
    fallback_started = time.perf_counter()
    try:
        fallback_result = await TTSOrchestrator(fallback_settings).synthesize(
            "Đây là bài kiểm tra chuyển sang giọng dự phòng."
        )
        fallback_drill = {
            "passed": fallback_result.fallback_used
            and fallback_result.voice == "vi-VN-NamMinhNeural"
            and bool(fallback_result.audio),
            "voice": fallback_result.voice,
            "fallback_used": fallback_result.fallback_used,
            "latency_ms": round((time.perf_counter() - fallback_started) * 1000),
            "audio_bytes": len(fallback_result.audio),
            "duration_ms": fallback_result.duration_ms,
        }
    except Exception as exc:
        fallback_drill = {
            "passed": False,
            "latency_ms": round((time.perf_counter() - fallback_started) * 1000),
            "error_type": type(exc).__name__,
        }

    orchestrator = TTSOrchestrator(voice_settings)
    rows: list[dict[str, object]] = []
    for case_id, text, critical_words in CASES:
        started = time.perf_counter()
        try:
            result = await orchestrator.synthesize(text)
            decoded = await asyncio.to_thread(decode_audio, result.audio, settings=asr_settings)
            asr = await asyncio.to_thread(runtime.transcribe, decoded.samples)
            spoken = result.spoken_text or text
            normalized_transcript = normalize(asr.text)
            preserved = [word for word in critical_words if normalize(word) in normalized_transcript]
            row = {
                "case_id": case_id,
                "voice": result.voice,
                "fallback_used": result.fallback_used,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "audio_bytes": len(result.audio),
                "duration_ms": result.duration_ms,
                "review_decision": result.review_decision,
                "review_reason_codes": result.review_reason_codes,
                "roundtrip_transcript": asr.text,
                "roundtrip_confidence": asr.confidence,
                "wer": round(error_rate(spoken, asr.text), 4),
                "cer": round(error_rate(spoken, asr.text, characters=True), 4),
                "critical_words": list(critical_words),
                "critical_words_preserved": preserved,
                "technical_audio": result.audio_metrics,
            }
            row["passed"] = (
                bool(asr.text.strip())
                and (asr.confidence or 0) >= 0.2
                and len(preserved) == len(critical_words)
            )
        except Exception as exc:
            row = {
                "case_id": case_id,
                "voice": None,
                "fallback_used": False,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "wer": 1.0,
                "cer": 1.0,
                "critical_words": list(critical_words),
                "critical_words_preserved": [],
                "error_type": type(exc).__name__,
                "passed": False,
            }
        rows.append(row)
        print(
            f"{case_id}: voice={row.get('voice')} fallback={row['fallback_used']} "
            f"latency_ms={row['latency_ms']} wer={row['wer']} passed={row['passed']}"
        )

    latencies = [float(row["latency_ms"]) for row in rows]
    report = {
        "generated_at_epoch": int(time.time()),
        "provider": "edge-tts",
        "provider_version": "7.2.8",
        "asr_review_model": asr_settings.asr_model_id,
        "voice_matrix": voice_matrix,
        "fallback_drill": fallback_drill,
        "summary": {
            "cases": len(rows),
            "passed": sum(bool(row["passed"]) for row in rows),
            "fallback_rate": round(statistics.fmean(bool(row["fallback_used"]) for row in rows), 4),
            "mean_wer": round(statistics.fmean(float(row["wer"]) for row in rows), 4),
            "mean_cer": round(statistics.fmean(float(row["cer"]) for row in rows), 4),
            "p50_latency_ms": round(percentile(latencies, 0.5), 2),
            "p95_latency_ms": round(percentile(latencies, 0.95), 2),
            "error_rate": round(1 - statistics.fmean(bool(row["passed"]) for row in rows), 4),
        },
        "method": "Real Edge-TTS audio, real FFprobe/FFmpeg technical validation, then real local ZipFormer ASR.",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if bool(fallback_drill["passed"]) and all(bool(row["passed"]) for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
