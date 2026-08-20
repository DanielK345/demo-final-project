"""Curated Vietnamese grapheme/phoneme confusions used as rewrite evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_ASR_CONFUSION_PATH = Path("data/gazetteer/vietnamese_asr_confusions.json")


@dataclass(frozen=True)
class ASRConfusion:
    canonical: str
    asr_variants: tuple[str, ...]
    scope: str
    examples: tuple[str, ...] = ()


class ASRConfusionCatalog:
    def __init__(self, entries: list[ASRConfusion]) -> None:
        self.entries = entries

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: str | Path = DEFAULT_ASR_CONFUSION_PATH) -> ASRConfusionCatalog:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls([])
        items = raw.get("confusions", []) if isinstance(raw, dict) else []
        entries: list[ASRConfusion] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            canonical = item.get("canonical")
            variants = item.get("asr_variants")
            if not isinstance(canonical, str) or not canonical.strip() or not isinstance(variants, list):
                continue
            cleaned_variants = tuple(
                value.strip() for value in variants if isinstance(value, str) and value.strip()
            )
            if not cleaned_variants:
                continue
            examples = item.get("examples")
            entries.append(
                ASRConfusion(
                    canonical=canonical.strip(),
                    asr_variants=cleaned_variants,
                    scope=str(item.get("scope") or "unspecified")[:40],
                    examples=tuple(
                        value[:120] for value in examples if isinstance(value, str) and value.strip()
                    )
                    if isinstance(examples, list)
                    else (),
                )
            )
        return cls(entries)

    def as_prompt_memory(self) -> list[dict[str, object]]:
        return [
            {
                "canonical": entry.canonical,
                "asr_variants": list(entry.asr_variants),
                "scope": entry.scope,
                "examples": list(entry.examples),
            }
            for entry in self.entries
        ]
