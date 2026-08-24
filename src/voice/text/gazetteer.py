"""Gazetteer địa danh dùng chung — Phần 4 (`docs/voice-ai/voice-runtime-architecture.md` §4).

Dùng ở 2 nơi: `asr/biasing.py` (fuzzy correction transcript + prompt hint cho
Groq, `asr/groq_provider.py`) và `tts/pronunciation.py` (Phần 6, chưa
implement — API ở đây đủ tổng quát để Phần 6 dùng lại, không cần sửa class
này khi Phần 6 làm).

`data/gazetteer/place_names.json` trong repo là **dữ liệu seed** (hơn 50
địa danh Hà Nội phổ biến, lấy làm ví dụ) — **chưa phải danh sách thật của
AloSM**. Xem `mustdo.md` — đội vận hành cần cung cấp danh sách
đầy đủ trước khi dùng cho demo/production thật.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_GAZETTEER_PATH = Path("data/gazetteer/place_names.json")


class Gazetteer:
    def __init__(self, entries: list[str]) -> None:
        seen: set[str] = set()
        unique: list[str] = []
        for raw in entries:
            entry = raw.strip()
            if entry and entry not in seen:
                seen.add(entry)
                unique.append(entry)
        self.entries: list[str] = unique

    @classmethod
    def load(cls, path: str | Path = DEFAULT_GAZETTEER_PATH) -> Gazetteer:
        """Không raise nếu file chưa tồn tại — trả gazetteer rỗng (pipeline
        vẫn chạy được, chỉ là không bias/sửa địa danh gì)."""
        path = Path(path)
        if not path.exists():
            return cls(entries=[])
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("place_names", []) if isinstance(data, dict) else data
        return cls(entries=entries)

    def as_prompt_hint(self, limit: int = 50) -> str:
        """Chuỗi ngắn gọn chèn vào `prompt` của Groq để bias nhận dạng địa danh."""
        return ", ".join(self.entries[:limit])

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, item: str) -> bool:
        return item in self.entries
