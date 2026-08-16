from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

_PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z0-9_]*_\d+>")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_NEGATIONS = {"không", "chưa", "đừng", "chẳng", "khỏi"}
_CONFIRMATIONS = {"xác nhận", "đồng ý", "có đặt", "đặt đi"}
_CANCELLATIONS = {"hủy", "huỷ"}


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _levenshtein(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, start=1):
        current = [i]
        for j, right_item in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def _rate(expected: list[str], actual: list[str]) -> float:
    return _levenshtein(expected, actual) / max(1, len(expected))


def _semantic_signature(text: str) -> tuple[bool, bool, bool]:
    normalized = _normalize(text)
    words = set(_WORD_RE.findall(normalized))
    has_negation = bool(words & _NEGATIONS)
    has_confirmation = any(phrase in normalized for phrase in _CONFIRMATIONS)
    has_cancellation = bool(words & _CANCELLATIONS)
    return has_negation, has_confirmation, has_cancellation


@dataclass(frozen=True, slots=True)
class RewriteCaseResult:
    case_id: str
    wer: float
    cer: float
    entity_errors: int
    entity_total: int
    false_corrections: int
    semantic_flip: bool
    pii_placeholder_violation: bool
    latency_ms: float | None
    cost_usd: float | None


def evaluate_case(sample: dict[str, Any]) -> RewriteCaseResult:
    case_id = str(sample.get("case_id") or "").strip()
    expected = str(sample.get("ground_truth") or "")
    raw = str(sample.get("raw_transcript") or "")
    rewritten = str(sample.get("rewritten_transcript") or "")
    if not case_id or not expected or not rewritten:
        raise ValueError("case_id, ground_truth and rewritten_transcript are required")

    expected_words = _WORD_RE.findall(_normalize(expected))
    rewritten_words = _WORD_RE.findall(_normalize(rewritten))
    expected_chars = list(_normalize(expected).replace(" ", ""))
    rewritten_chars = list(_normalize(rewritten).replace(" ", ""))

    entities = sample.get("entities") or []
    entity_errors = 0
    for entity in entities:
        if not isinstance(entity, dict) or not str(entity.get("value") or "").strip():
            raise ValueError(f"invalid entity annotation in case {case_id}")
        if _normalize(str(entity["value"])) not in _normalize(rewritten):
            entity_errors += 1

    raw_words = _WORD_RE.findall(_normalize(raw))
    unchanged_truth = Counter(raw_words) & Counter(expected_words)
    rewritten_counts = Counter(rewritten_words)
    false_corrections = sum(max(0, count - rewritten_counts[word]) for word, count in unchanged_truth.items())

    expected_placeholders = Counter(_PLACEHOLDER_RE.findall(expected))
    rewritten_placeholders = Counter(_PLACEHOLDER_RE.findall(rewritten))
    return RewriteCaseResult(
        case_id=case_id,
        wer=_rate(expected_words, rewritten_words),
        cer=_rate(expected_chars, rewritten_chars),
        entity_errors=entity_errors,
        entity_total=len(entities),
        false_corrections=false_corrections,
        semantic_flip=_semantic_signature(expected) != _semantic_signature(rewritten),
        pii_placeholder_violation=expected_placeholders != rewritten_placeholders,
        latency_ms=float(sample["latency_ms"]) if sample.get("latency_ms") is not None else None,
        cost_usd=float(sample["cost_usd"]) if sample.get("cost_usd") is not None else None,
    )


def evaluate_dataset(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        raise ValueError("rewrite evaluation dataset must not be empty")
    results = [evaluate_case(sample) for sample in samples]
    entity_errors = sum(item.entity_errors for item in results)
    entity_total = sum(item.entity_total for item in results)
    semantic_flips = sum(item.semantic_flip for item in results)
    pii_violations = sum(item.pii_placeholder_violation for item in results)
    latencies = sorted(item.latency_ms for item in results if item.latency_ms is not None)
    costs = [item.cost_usd for item in results if item.cost_usd is not None]
    hard_gate_passed = semantic_flips == 0 and pii_violations == 0
    return {
        "case_count": len(results),
        "mean_wer": sum(item.wer for item in results) / len(results),
        "mean_cer": sum(item.cer for item in results) / len(results),
        "entity_error_rate": entity_errors / max(1, entity_total),
        "false_correction_count": sum(item.false_corrections for item in results),
        "semantic_flip_count": semantic_flips,
        "pii_placeholder_violation_count": pii_violations,
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "total_cost_usd": sum(costs) if costs else None,
        "hard_gate_passed": hard_gate_passed,
        "cases": [item.__dict__ if hasattr(item, "__dict__") else {
            field: getattr(item, field) for field in item.__dataclass_fields__
        } for item in results],
    }


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, round((len(values) - 1) * quantile)))
    return values[index]
