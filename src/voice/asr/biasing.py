"""Fuzzy correction địa danh sau ASR — Phần 4 (`docs/voice_ai_overview.md` §6).

Kết hợp với prompt-conditioning (`asr/groq_provider.py` nhận `prompt_hint`
từ cùng `Gazetteer`) — hai cách không loại trừ nhau, dùng cả hai để tăng độ
chính xác tổng thể (đúng quyết định đã chốt trong overview).

**Phạm vi:** so khớp mờ chỉ giữa các cụm từ **cùng số từ** với địa danh
gazetteer (vd. lỗi thiếu dấu "vincom dong khoi" -> "Vincom Đồng Khởi", cả
hai đều 3 từ). Cách này cố tình đánh đổi: **không** tự sửa lỗi ASR tách một
từ thành nhiều từ (vd. "Vin Côm" — 2 từ — thay vì "Vincom" — 1 từ). Muốn xử
lý case tách từ, cần thêm bước ghép thử các cặp token liền kề trước khi so
khớp — chưa làm, ghi trong `docs/mustdo_voice.md`.

**Cách chấm điểm:** so khớp *theo từng từ một, đúng vị trí* (span từ thứ i
so với candidate từ thứ i), lấy điểm THẤP NHẤT trong các cặp từ làm điều
kiện chấp nhận — không dùng `fuzz.ratio` trên cả cụm nối lại. Lý do: ratio
trên cụm nối lại dễ bị "ăn gian" bởi 1 từ dài trùng khớp (vd. "landmark")
kéo điểm tổng lên cao dù từ còn lại ("ở") hoàn toàn không liên quan — đã
tự phát hiện bug này khi viết test cho module (xem
`tests/test_voice/test_biasing.py::test_never_eats_a_neighboring_unrelated_word`
và test tương tự cho "landmark 81"). So khớp theo từng từ tránh được lỗi đó
vì một từ lạc lõng sẽ kéo điểm thấp nhất xuống rất thấp, bị loại ngay.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from src.voice.text.gazetteer import Gazetteer

_WORD_RE = re.compile(r"\S+")


def _word_aligned_score(span_words: list[str], candidate_words: list[str]) -> float:
    """Điểm thấp nhất trong các cặp từ (span[i], candidate[i]) cùng vị trí."""
    return min(fuzz.ratio(a.lower(), b.lower()) for a, b in zip(span_words, candidate_words, strict=True))


def correct_place_names(
    text: str,
    gazetteer: Gazetteer,
    *,
    score_cutoff: float = 45.0,
) -> str:
    """Thay các cụm từ gần đúng địa danh trong `text` bằng dạng chuẩn trong
    gazetteer.

    Với mỗi độ dài (số từ) xuất hiện trong gazetteer, quét mọi cửa sổ liền
    kề có đúng độ dài đó; so khớp theo từng từ (`_word_aligned_score`) với
    từng địa danh cùng độ dài, chọn candidate có điểm trung bình cao nhất
    trong số các candidate đạt `score_cutoff`. Xử lý từ địa danh dài nhất
    tới ngắn nhất; span đã được thay không bị chọn lại (không chồng lấp).
    """
    if not gazetteer.entries or not text.strip():
        return text

    tokens = list(_WORD_RE.finditer(text))
    n = len(tokens)
    if n == 0:
        return text

    entries_by_length: dict[int, list[list[str]]] = {}
    for entry in gazetteer.entries:
        words = entry.split()
        entries_by_length.setdefault(len(words), []).append(words)

    claimed = [False] * n
    replacements: list[tuple[int, int, str]] = []

    for window in sorted(entries_by_length, reverse=True):
        if window == 0 or window > n:
            continue
        candidates = entries_by_length[window]
        for start in range(0, n - window + 1):
            if any(claimed[start : start + window]):
                continue
            span_words = [text[tokens[i].start() : tokens[i].end()] for i in range(start, start + window)]

            best_candidate: list[str] | None = None
            best_avg = -1.0
            for candidate_words in candidates:
                min_score = _word_aligned_score(span_words, candidate_words)
                if min_score < score_cutoff:
                    continue
                avg_score = sum(
                    fuzz.ratio(a.lower(), b.lower()) for a, b in zip(span_words, candidate_words, strict=True)
                ) / window
                if avg_score > best_avg:
                    best_avg = avg_score
                    best_candidate = candidate_words

            if best_candidate is None:
                continue

            replacement = " ".join(best_candidate)
            span_text = text[tokens[start].start() : tokens[start + window - 1].end()]
            if replacement.lower() == span_text.lower():
                continue  # đã đúng sẵn, không cần "sửa"

            for i in range(start, start + window):
                claimed[i] = True
            replacements.append((tokens[start].start(), tokens[start + window - 1].end(), replacement))

    if not replacements:
        return text

    replacements.sort(key=lambda item: item[0])
    pieces: list[str] = []
    cursor = 0
    for start_char, end_char, replacement in replacements:
        pieces.append(text[cursor:start_char])
        pieces.append(replacement)
        cursor = end_char
    pieces.append(text[cursor:])
    return "".join(pieces)
