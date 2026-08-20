"""Curated Vietnamese grapheme/phoneme confusions used as rewrite evidence."""

from __future__ import annotations

import json
import re
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

    def generate_variants(
        self,
        text: str,
        *,
        max_substitutions: int = 2,
        max_variants: int = 128,
    ) -> set[str]:
        """Generate bounded context variants without exponential expansion."""

        variants = {text}
        frontier = {text}
        for _ in range(max_substitutions):
            expanded: set[str] = set()
            for value in frontier:
                for entry in self.entries:
                    expanded.update(self._single_substitutions(value, entry))
                    if len(variants) + len(expanded) >= max_variants:
                        break
                if len(variants) + len(expanded) >= max_variants:
                    break
            expanded -= variants
            if not expanded:
                break
            remaining = max_variants - len(variants)
            frontier = set(sorted(expanded)[:remaining])
            variants.update(frontier)
            if len(variants) >= max_variants:
                break
        return variants

    @staticmethod
    def _single_substitutions(text: str, entry: ASRConfusion) -> set[str]:
        # Tone classes are useful LLM evidence but are not literal substrings.
        if entry.scope == "tone_class":
            return set()
        escaped = re.escape(entry.canonical)
        if entry.scope == "syllable_onset":
            pattern = re.compile(rf"(?<!\w){escaped}", re.IGNORECASE)
        elif entry.scope in {"syllable_coda", "syllable_rhyme"}:
            pattern = re.compile(rf"{escaped}(?!\w)", re.IGNORECASE)
        else:
            pattern = re.compile(escaped, re.IGNORECASE)
        variants: set[str] = set()
        for match in pattern.finditer(text):
            for replacement in entry.asr_variants:
                variants.add(text[: match.start()] + replacement + text[match.end() :])
        return variants
