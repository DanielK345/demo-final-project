"""Chuẩn hoá transcript trước khi đưa vào Core Agent — Phần 4
(`docs/voice-ai/voice-runtime-architecture.md` §5/§6, Ref `S1-6`).

Phạm vi đã hỗ trợ (đủ cho các câu thường gặp khi đặt xe/tra cứu chuyến):

- Gộp khoảng trắng thừa, trim.
- Bỏ các từ đệm đứng riêng, rõ ràng không mang nghĩa ("ừm", "ờ"...).
- Số đếm cơ bản (1-99, kể cả dạng "mười ba"/"hai mươi lăm") ghép với **một**
  đơn vị (trăm/nghìn/ngàn/triệu) → số + dấu chấm ngăn cách nghìn, ví dụ
  "hai mươi nghìn đồng" → "20.000 đồng".

**Cố tình KHÔNG** tự động số hoá một từ số đơn lẻ không có đơn vị đi kèm
(vd. "năm", "ba", "một" đứng một mình) — những từ này quá dễ nhầm với nghĩa
khác trong tiếng Việt ("năm nay" = năm/year, "ba" = bố/dad...) nên **không
đoán bừa** (đúng nguyên tắc BR-002 — không tự suy diễn thông tin).

**CHƯA hỗ trợ:** số ghép nhiều bậc đơn vị trong cùng một cụm (vd. "một trăm
nghìn" = 100.000 sẽ chỉ được chuẩn hoá thành "100 nghìn", không gộp tiếp
thành "100.000") — đây là bài tập capstone, ưu tiên các mẫu hay gặp thực tế,
mở rộng dần khi gặp câu thật xử lý sai (Tuần 4/5, xem `mustdo.md`).
"""

from __future__ import annotations

import re

_FILLER_WORDS = {"ừm", "ờ", "ơ", "ừ"}

_ONES_WORDS = {
    "không": 0,
    "một": 1,
    "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "tư": 4,
    "năm": 5,
    "lăm": 5,
    "sáu": 6,
    "bảy": 7,
    "tám": 8,
    "chín": 9,
}
_MAGNITUDE_WORDS = {"trăm": 100, "nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000}

_WHITESPACE_RE = re.compile(r"\s+")

_ONES_PATTERN = "|".join(sorted(_ONES_WORDS, key=len, reverse=True))
_MAGNITUDE_PATTERN = "|".join(_MAGNITUDE_WORDS)
_BASE_NUMBER_PATTERN = (
    rf"(?:mười(?:\s+(?:{_ONES_PATTERN}))?"
    rf"|(?:{_ONES_PATTERN})\s+mươi(?:\s+(?:{_ONES_PATTERN}))?"
    rf"|{_ONES_PATTERN})"
)
_NUMBER_PHRASE_RE = re.compile(
    rf"\b({_BASE_NUMBER_PATTERN})(?:\s+({_MAGNITUDE_PATTERN}))?\b",
    re.IGNORECASE,
)


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_fillers(text: str) -> str:
    tokens = text.split(" ")
    kept = [t for t in tokens if t.strip(",.!?").lower() not in _FILLER_WORDS]
    return " ".join(kept)


def _parse_base_number(phrase: str) -> int | None:
    """Parse số 0-99 dạng chữ. Trả None nếu không parse được (giữ nguyên
    text gốc — an toàn hơn là đoán sai)."""
    words = phrase.lower().split()
    if len(words) == 1:
        word = words[0]
        if word == "mười":
            return 10
        return _ONES_WORDS.get(word)
    if len(words) == 2:
        if words[0] == "mười" and words[1] in _ONES_WORDS:
            return 10 + _ONES_WORDS[words[1]]
        if words[1] == "mươi" and words[0] in _ONES_WORDS:
            return _ONES_WORDS[words[0]] * 10
        return None
    if len(words) == 3 and words[1] == "mươi" and words[0] in _ONES_WORDS and words[2] in _ONES_WORDS:
        return _ONES_WORDS[words[0]] * 10 + _ONES_WORDS[words[2]]
    return None


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _normalize_numbers(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        base_phrase = match.group(1)
        magnitude_word = match.group(2)
        base_value = _parse_base_number(base_phrase)
        if base_value is None:
            return match.group(0)

        is_unambiguous_multiword = len(base_phrase.split()) >= 2
        if magnitude_word is None and not is_unambiguous_multiword:
            # Số 1 chữ đứng riêng, không đơn vị -> quá dễ nhầm nghĩa khác, không đổi.
            return match.group(0)

        # match.group(0) chứa cả base number lẫn magnitude_word (nếu có) -> giá
        # trị đã nhân sẵn đủ để thay thế toàn bộ span, không cần nối lại magnitude_word.
        value = base_value * _MAGNITUDE_WORDS[magnitude_word.lower()] if magnitude_word else base_value
        return _format_number(value)

    return _NUMBER_PHRASE_RE.sub(_replace, text)


def normalize_transcript(text: str) -> str:
    if not text or not text.strip():
        return text
    normalized = _collapse_whitespace(text)
    normalized = _strip_fillers(normalized)
    normalized = _normalize_numbers(normalized)
    return _collapse_whitespace(normalized)
