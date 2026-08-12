"""Override phát âm tên riêng — Phần 6 (`docs/voice_ai_overview.md` §6, Ref `S2-3`).

Text substitution đơn giản (quyết định đã chốt — không dùng SSML): thay tên
thương hiệu/từ viết tắt khó đọc bằng cách viết ra cách đọc gần đúng trước
khi đưa vào TTS. Ví dụ đã có sẵn trong overview §6 (`AloSM` → `"Alo Ét Em"`,
`Landmark 81` → `"Len Mác Tám Mươi Mốt"`).

Khác với `asr/biasing.py` (Phần 4, sửa lỗi ASR *sau khi nghe*), module này
chạy *trước khi nói* — không dùng chung logic fuzzy-match, chỉ thay đúng
khớp (exact match, không phân biệt hoa/thường) vì đầu vào là text đã biết
trước (response của Core Agent), không phải transcript lẫn lỗi nhận dạng.
"""

from __future__ import annotations

import re

BRAND_PRONUNCIATIONS: dict[str, str] = {
    "AloSM": "Alo Ét Em",
    "Landmark 81": "Len Mác Tám Mươi Mốt",
}


def apply_pronunciation_overrides(
    text: str,
    *,
    overrides: dict[str, str] | None = None,
) -> str:
    """Thay các cụm khớp chính xác (không phân biệt hoa/thường) trong `text`
    bằng cách đọc đã override. Mặc định dùng `BRAND_PRONUNCIATIONS`; truyền
    `overrides` để thêm/ghi đè (vd. gộp thêm bảng phát âm riêng của đội vận
    hành mà không cần sửa module này).
    """
    if not text:
        return text

    table = dict(BRAND_PRONUNCIATIONS)
    if overrides:
        table.update(overrides)
    if not table:
        return text

    # Thay cụm dài nhất trước — tránh 1 cụm ngắn "ăn" mất 1 phần của cụm dài hơn.
    for original in sorted(table, key=len, reverse=True):
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        text = pattern.sub(table[original], text)
    return text
