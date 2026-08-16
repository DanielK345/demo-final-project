from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

# data/gazetteer/place_names.json đã có sẵn từ trước (dùng cho Voice ASR biasing, xem
# src/voice/text/gazetteer.py) — tái dùng đúng nguồn thật này cho search_place của Core
# Agent thay vì bịa candidate giả (bản cũ chỉ echo lại nguyên câu người dùng nhập thành
# 1 candidate duy nhất, không thật sự "tìm kiếm" gì cả).
_GAZETTEER_PATH = Path(__file__).resolve().parents[3] / "data" / "gazetteer" / "place_names.json"


@lru_cache
def _load_place_names() -> tuple[str, ...]:
    try:
        raw = json.loads(_GAZETTEER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    names = raw.get("place_names", [])
    return tuple(name for name in names if isinstance(name, str) and name.strip())


def place_id_for(display_name: str) -> str:
    """place_id ổn định (không random) theo tên đã chuẩn hoá — cùng 1 địa điểm luôn ra
    cùng 1 place_id giữa các lượt gọi, cần thiết để guardrails đối chiếu
    pickup_place_id/destination_place_id với state đã lưu (xem AgentGuardrails)."""
    digest = hashlib.sha256(display_name.strip().casefold().encode("utf-8")).hexdigest()
    return f"place_{digest[:12]}"


class PlaceSearchService:
    """search_place thật — khớp chuỗi con trên gazetteer địa danh thật (23 địa điểm nội
    thành TP.HCM, xem file gazetteer). Không có toạ độ thật trong gazetteer (chỉ có
    tên) nên không trả lat/lng giả; nơi cần khoảng cách (PricingService) tự suy ra
    deterministic từ place_id thay vì bịa GPS."""

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return []
        matches = [name for name in _load_place_names() if normalized_query in name.casefold()]
        if not matches:
            # Gazetteer không phải geocoder. Không echo free-form text thành place đã
            # resolve; caller phải hỏi lại hoặc dùng MapsProvider thật.
            return []
        return [
            {
                "place_id": place_id_for(name),
                "display_name": name,
                "address": name,
                "provider": "local_gazetteer",
                "provider_payload_version": "2026-08-16",
                "data_quality": "DEMO",
                "serviceable": None,
            }
            for name in matches[:limit]
        ]
