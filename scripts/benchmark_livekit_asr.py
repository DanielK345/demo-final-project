"""Offline ASR benchmark through the same official LiveKit STT used by the worker.

The manifest is JSONL. Each row must contain ``case_id``, ``dataset_version``,
``audio_path``, ``audio_sha256``, ``consent=true``, ``expected_transcript``, and
``expected_entities``. Optional ``accent`` and ``noise`` values define report
slices. Raw audio is read but never copied into the report directory.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from livekit.agents import stt
from livekit.agents.utils.audio import audio_frames_from_file

from src.voice_agent.config import get_livekit_voice_settings
from src.voice_agent.model_factory import build_stt


@dataclass(frozen=True, slots=True)
class ASRCase:
    case_id: str
    dataset_version: str
    audio_path: Path
    audio_sha256: str
    expected_transcript: str
    expected_entities: tuple[str, ...]
    accent: str
    noise: str


@dataclass(frozen=True, slots=True)
class ASRResult:
    case_id: str
    dataset_version: str
    audio_sha256: str
    accent: str
    noise: str
    provider: str
    model: str
    language: str
    transcript: str
    normalized_transcript: str
    expected_transcript: str
    normalized_expected_transcript: str
    wer: float
    cer: float
    entity_matches: dict[str, bool]
    entity_accuracy: float | None
    confidence: float | None
    audio_duration_seconds: float
    recognition_duration_ms: float


def normalize_text(value: str) -> str:
    """Normalize punctuation/spacing while preserving Vietnamese diacritics."""

    normalized = unicodedata.normalize("NFC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE).split())


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row_index, reference_item in enumerate(reference, 1):
        current = [row_index]
        for column_index, hypothesis_item in enumerate(hypothesis, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column_index] + 1,
                    previous[column_index - 1] + (reference_item != hypothesis_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: list[str], hypothesis: list[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return round(_edit_distance(reference, hypothesis) / len(reference), 4)


def _load_manifest(path: Path) -> list[ASRCase]:
    rows: list[ASRCase] = []
    seen_case_ids: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            raw = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        case_id = str(raw.get("case_id") or "").strip()
        if not case_id or case_id in seen_case_ids:
            raise ValueError(f"missing or duplicate case_id at {path}:{line_number}")
        if raw.get("consent") is not True:
            raise ValueError(f"case {case_id} is missing explicit audio consent")
        audio_value = str(raw.get("audio_path") or "").strip()
        audio_path = Path(audio_value)
        if not audio_path.is_absolute():
            audio_path = path.parent / audio_path
        entities = raw.get("expected_entities")
        if not isinstance(entities, list) or not all(isinstance(item, str) for item in entities):
            raise ValueError(f"case {case_id} expected_entities must be a string list")
        row = ASRCase(
            case_id=case_id,
            dataset_version=str(raw.get("dataset_version") or "").strip(),
            audio_path=audio_path.resolve(),
            audio_sha256=str(raw.get("audio_sha256") or "").lower(),
            expected_transcript=str(raw.get("expected_transcript") or "").strip(),
            expected_entities=tuple(entities),
            accent=str(raw.get("accent") or "unspecified"),
            noise=str(raw.get("noise") or "unspecified"),
        )
        if not row.dataset_version or not row.expected_transcript or len(row.audio_sha256) != 64:
            raise ValueError(f"case {case_id} is missing required ground-truth fields")
        rows.append(row)
        seen_case_ids.add(case_id)
    if not rows:
        raise ValueError("ASR manifest is empty")
    if len({row.dataset_version for row in rows}) != 1:
        raise ValueError("all ASR cases must use one dataset_version")
    return rows


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _decode_audio(path: Path) -> tuple[list[Any], float]:
    frames = [frame async for frame in audio_frames_from_file(str(path), sample_rate=16_000, num_channels=1)]
    duration = sum(frame.samples_per_channel / frame.sample_rate for frame in frames)
    if not frames:
        raise ValueError(f"decoded audio is empty: {path}")
    return frames, duration


async def benchmark_case(case: ASRCase, *, model: stt.STT, language: str) -> ASRResult:
    if not case.audio_path.is_file():
        raise FileNotFoundError(case.audio_path)
    if _file_sha256(case.audio_path) != case.audio_sha256:
        raise ValueError(f"audio hash mismatch for {case.case_id}")

    frames, audio_duration = await _decode_audio(case.audio_path)
    started = time.monotonic()
    event = await model.recognize(frames, language=language)
    recognition_duration_ms = round((time.monotonic() - started) * 1000, 3)
    alternative = event.alternatives[0] if event.alternatives else None
    transcript = alternative.text.strip() if alternative else ""
    normalized_reference = normalize_text(case.expected_transcript)
    normalized_hypothesis = normalize_text(transcript)
    reference_words = normalized_reference.split()
    hypothesis_words = normalized_hypothesis.split()
    reference_chars = list(normalized_reference.replace(" ", ""))
    hypothesis_chars = list(normalized_hypothesis.replace(" ", ""))
    entity_matches = {
        entity: normalize_text(entity) in normalized_hypothesis
        for entity in case.expected_entities
    }
    entity_accuracy = (
        round(sum(entity_matches.values()) / len(entity_matches), 4)
        if entity_matches
        else None
    )
    return ASRResult(
        case_id=case.case_id,
        dataset_version=case.dataset_version,
        audio_sha256=case.audio_sha256,
        accent=case.accent,
        noise=case.noise,
        provider=model.provider,
        model=model.model,
        language=language,
        transcript=transcript,
        normalized_transcript=normalized_hypothesis,
        expected_transcript=case.expected_transcript,
        normalized_expected_transcript=normalized_reference,
        wer=error_rate(reference_words, hypothesis_words),
        cer=error_rate(reference_chars, hypothesis_chars),
        entity_matches=entity_matches,
        entity_accuracy=entity_accuracy,
        confidence=round(alternative.confidence, 4) if alternative else None,
        audio_duration_seconds=round(audio_duration, 3),
        recognition_duration_ms=recognition_duration_ms,
    )


def _summary(results: list[ASRResult]) -> dict[str, object]:
    slices: dict[str, list[ASRResult]] = defaultdict(list)
    for result in results:
        slices["all"].append(result)
        slices[f"accent:{result.accent}"].append(result)
        slices[f"noise:{result.noise}"].append(result)

    def summarize(rows: list[ASRResult]) -> dict[str, object]:
        entity_count = sum(len(row.entity_matches) for row in rows)
        entity_match_count = sum(sum(row.entity_matches.values()) for row in rows)
        return {
            "case_count": len(rows),
            "mean_wer": round(sum(row.wer for row in rows) / len(rows), 4),
            "mean_cer": round(sum(row.cer for row in rows) / len(rows), 4),
            "entity_accuracy": (
                round(entity_match_count / entity_count, 4) if entity_count else None
            ),
            "no_transcript_rate": round(sum(not row.transcript for row in rows) / len(rows), 4),
        }

    first = results[0]
    return {
        "schema_version": "1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": first.dataset_version,
        "provider": first.provider,
        "model": first.model,
        "language": first.language,
        "slices": {name: summarize(rows) for name, rows in sorted(slices.items())},
    }


async def run(manifest: Path, output_dir: Path) -> None:
    cases = _load_manifest(manifest)
    results_path = output_dir / "asr-results.jsonl"
    summary_path = output_dir / "asr-summary.json"
    if results_path.exists() or summary_path.exists():
        raise FileExistsError(f"refusing to overwrite ASR evidence in {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = get_livekit_voice_settings()
    settings.require_stt_configured()
    model = build_stt(settings)
    results: list[ASRResult] = []
    try:
        for case in cases:
            result = await benchmark_case(case, model=model, language=settings.livekit_stt_language)
            results.append(result)
            with results_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(asdict(result), ensure_ascii=False, separators=(",", ":")) + "\n")
            print(f"LIVEKIT_ASR_CASE={case.case_id} WER={result.wer} CER={result.cer}")
    finally:
        await model.aclose()
    summary_path.write_text(json.dumps(_summary(results), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    asyncio.run(run(arguments.manifest, arguments.output_dir))
