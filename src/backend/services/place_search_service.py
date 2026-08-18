from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

# data/gazetteer/place_names.json đã có sẵn từ trước (dùng cho Voice ASR biasing, xem
# src/voice/text/gazetteer.py) — tái dùng đúng nguồn thật này cho search_place của Core
# Agent thay vì bịa candidate giả (bản cũ chỉ echo lại nguyên câu người dùng nhập thành
# 1 candidate duy nhất, không thật sự "tìm kiếm" gì cả).
_GAZETTEER_PATH = Path(__file__).resolve().parents[3] / "data" / "gazetteer" / "place_names.json"
_ALIASES_PATH = Path(__file__).resolve().parents[3] / "data" / "gazetteer" / "hanoi_place_aliases.json"
_LANDMARK_PICKUP_POINTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "gazetteer"
    / "hanoi_landmark_pickup_points.json"
)


@lru_cache
def _load_place_names() -> tuple[str, ...]:
    try:
        raw = json.loads(_GAZETTEER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    names = raw.get("place_names", [])
    return tuple(name for name in names if isinstance(name, str) and name.strip())


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_marks).split())


@lru_cache
def _load_aliases() -> dict[str, str]:
    """Map normalized Hanoi aliases to canonical names in the active gazetteer."""
    try:
        raw = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    active_names = set(_load_place_names())
    aliases: dict[str, str] = {}
    for item in raw.get("entries", []):
        if not isinstance(item, dict):
            continue
        canonical = item.get("canonical_name")
        if not isinstance(canonical, str) or canonical not in active_names:
            continue
        aliases[_normalize(canonical)] = canonical
        for alias in item.get("asr_aliases", []):
            if isinstance(alias, str) and alias.strip():
                aliases.setdefault(_normalize(alias), canonical)
    return aliases


@lru_cache
def _load_landmark_pickup_points() -> dict[str, tuple[dict[str, str], ...]]:
    """Load explicit pickup/drop-off choices for the two intentionally ambiguous landmarks."""
    try:
        raw = json.loads(_LANDMARK_PICKUP_POINTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    version = str(raw.get("version", "hanoi-landmark-pickup-points-v1"))
    landmarks: dict[str, tuple[dict[str, str], ...]] = {}
    for landmark in raw.get("landmarks", []):
        if not isinstance(landmark, dict):
            continue
        canonical_name = landmark.get("canonical_name")
        if not isinstance(canonical_name, str) or not canonical_name.strip():
            continue
        candidates: list[dict[str, str]] = []
        for point in landmark.get("pickup_points", []):
            if not isinstance(point, dict):
                continue
            name = point.get("name")
            address = point.get("address")
            maps_url = point.get("google_maps_url")
            aliases = point.get("asr_aliases")
            if not isinstance(name, str) or not isinstance(address, str):
                continue
            cleaned_aliases = [
                alias.strip()
                for alias in aliases
                if isinstance(alias, str) and alias.strip()
            ] if isinstance(aliases, list) else []
            candidates.append(
                {
                    "place_id": place_id_for(f"{canonical_name}:{name}:{address}"),
                    "display_name": name,
                    "address": address,
                    "provider": "local_landmark_mock",
                    "provider_payload_version": version,
                    "data_quality": "MOCK_VERIFIED_FROM_PUBLIC_SOURCES",
                    "serviceable": None,
                    "city": "Hà Nội",
                    "parent_landmark": canonical_name,
                    "google_maps_url": maps_url if isinstance(maps_url, str) else "",
                    "asr_aliases": cleaned_aliases,
                }
            )
        if len(candidates) >= 2:
            landmarks[canonical_name] = tuple(candidates)
    return landmarks


def place_id_for(display_name: str) -> str:
    """place_id ổn định (không random) theo tên đã chuẩn hoá — cùng 1 địa điểm luôn ra
    cùng 1 place_id giữa các lượt gọi, cần thiết để guardrails đối chiếu
    pickup_place_id/destination_place_id với state đã lưu (xem AgentGuardrails)."""
    digest = hashlib.sha256(display_name.strip().casefold().encode("utf-8")).hexdigest()
    return f"place_{digest[:12]}"


def _fuzzy_canonical_match(normalized_query: str) -> str | None:
    """Resolve a single high-confidence gazetteer name without inventing a place.

    Every returned place still has to be confirmed through the LiveKit task's
    ``select_place`` tool. Ambiguous or weak matches deliberately return ``None``.
    """

    if len(normalized_query.split()) < 2:
        return None

    scores: dict[str, float] = {}
    for name in _load_place_names():
        scores[name] = fuzz.WRatio(normalized_query, _normalize(name))
    for alias, canonical in _load_aliases().items():
        scores[canonical] = max(scores.get(canonical, 0), fuzz.WRatio(normalized_query, alias))

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ranked or ranked[0][1] < 92.5:
        return None
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0
    if ranked[0][1] - runner_up_score < 5:
        return None
    return ranked[0][0]


class PlaceSearchService:
    """Demo search for the Hanoi seed gazetteer and its known ASR aliases.

    Không có toạ độ thật trong gazetteer (chỉ có
    tên) nên không trả lat/lng giả; nơi cần khoảng cách (PricingService) tự suy ra
    deterministic từ place_id thay vì bịa GPS."""

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        normalized_query = _normalize(query)
        if not normalized_query:
            return []
        alias_match = _load_aliases().get(normalized_query)
        if alias_match:
            matches = [alias_match]
        else:
            matches = [
                name
                for name in _load_place_names()
                if normalized_query in _normalize(name) or _normalize(name) in normalized_query
            ]
        match_provider = "local_gazetteer"
        if not matches:
            fuzzy_match = _fuzzy_canonical_match(normalized_query)
            matches = [fuzzy_match] if fuzzy_match else []
            match_provider = "local_gazetteer_fuzzy"
        if not matches:
            # Gazetteer không phải geocoder. Không echo free-form text thành place đã
            # resolve; caller phải hỏi lại hoặc dùng MapsProvider thật.
            return []
        if len(matches) == 1:
            landmark_candidates = _load_landmark_pickup_points().get(matches[0])
            if landmark_candidates:
                return [dict(candidate) for candidate in landmark_candidates[:limit]]
        return [
            {
                "place_id": place_id_for(name),
                "display_name": name,
                "address": name,
                "provider": match_provider,
                "provider_payload_version": "hanoi-v2-2026-08-16",
                "data_quality": "DEMO",
                "serviceable": None,
                "city": "Hà Nội",
            }
            for name in matches[:limit]
        ]
