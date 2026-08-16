"""Deterministic corrections for known Vietnamese ASR place-name confusions.

Unlike an LLM, this table is deterministic and works even when the rewrite
provider is unavailable.  Entries are deliberately complete phrases so a short,
ambiguous word (for example a district name) is never expanded into a landmark.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_PLACE_ALIAS_PATH = Path("data/gazetteer/hanoi_place_aliases.json")


@dataclass(frozen=True)
class PlaceAlias:
    canonical_name: str
    asr_aliases: tuple[str, ...]


class PlaceAliasCatalog:
    def __init__(self, entries: list[PlaceAlias]) -> None:
        self.entries = entries
        replacements: list[tuple[re.Pattern[str], str]] = []
        seen_aliases: set[str] = set()
        for entry in entries:
            for alias in entry.asr_aliases:
                key = " ".join(alias.casefold().split())
                if not key or key == entry.canonical_name.casefold() or key in seen_aliases:
                    continue
                seen_aliases.add(key)
                # Word boundaries prevent replacing a part of another token.  Whitespace
                # is flexible because ASR can insert extra spaces between syllables.
                escaped = re.escape(alias).replace(r"\ ", r"\s+")
                replacements.append((re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE), entry.canonical_name))
        self._replacements = sorted(replacements, key=lambda item: len(item[0].pattern), reverse=True)

    @classmethod
    @lru_cache(maxsize=4)
    def load(cls, path: str | Path = DEFAULT_PLACE_ALIAS_PATH) -> "PlaceAliasCatalog":
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls([])

        raw_entries = raw.get("entries", []) if isinstance(raw, dict) else []
        entries: list[PlaceAlias] = []
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            canonical = item.get("canonical_name")
            aliases = item.get("asr_aliases")
            if not isinstance(canonical, str) or not canonical.strip() or not isinstance(aliases, list):
                continue
            cleaned_aliases = tuple(alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip())
            entries.append(PlaceAlias(canonical.strip(), cleaned_aliases))
        return cls(entries)

    @property
    def canonical_names(self) -> list[str]:
        return [entry.canonical_name for entry in self.entries]

    def correct(self, text: str) -> str:
        corrected = text
        for pattern, canonical_name in self._replacements:
            corrected = pattern.sub(canonical_name, corrected)
        return corrected

