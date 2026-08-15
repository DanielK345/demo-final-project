"""Spoken-language formatter cho TTS — Phần 6 (`docs/voice-ai/voice_ai_overview.md` §5/§6, Ref `S1-7`).

Chiều **ngược lại** với `text/normalizer.py` (Phần 4): Core Agent trả response
text có thể chứa số dạng chữ số (giá cước, ETA, khoảng cách — vd `"20.000
đồng"`, `"15 phút"`, `"3,5 km"`) — đọc thẳng số ra TTS thường nghe cộc/không
tự nhiên (provider tuỳ chọn có thể đọc "hai không không không không đồng").
Module này biến số thành câu đọc tự nhiên trước khi đưa vào TTS.

Quy ước số Việt Nam: dấu **chấm** = phân tách hàng nghìn (`"20.000"` =
20 000), dấu **phẩy** = phân tách phần thập phân (`"3,5"` = 3.5) — ngược với
tiếng Anh. Số thập phân được đọc từng chữ số sau dấu phẩy (quy ước phổ biến
cho số đo, tránh nhập nhằng "ba phẩy năm mươi" vs "ba phẩy năm không").

**Phạm vi đã hỗ trợ:** số nguyên 0 - 999,999,999 (đủ cho giá cước/ETA/số
đếm trong hội thoại đặt xe), số thập phân 1 chữ số sau dấu phẩy trở lên
(đọc từng chữ số). **Chưa hỗ trợ:** số âm ngoài ngữ cảnh tiền tệ, phân số,
ngày/giờ/tháng (không phải phạm vi của module này).
"""

from __future__ import annotations

import re

_ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_SCALE_WORDS = ["", "nghìn", "triệu", "tỷ"]

_INTEGER_RE = re.compile(r"(?<![\d,])\d{1,3}(?:\.\d{3})*(?![\d.,])")
_DECIMAL_RE = re.compile(r"\b(\d+),(\d+)\b")


def _read_three_digits(n: int, *, is_leading_group: bool) -> str:
    """Đọc số 0-999 thành chữ. `is_leading_group`: nhóm 3 chữ số cao nhất
    (không có nhóm nào phía trước) — nhóm dẫn đầu không cần đọc "không trăm"
    khi hàng trăm = 0.
    """
    if n == 0:
        return "" if is_leading_group else "không trăm"

    hundreds, remainder = divmod(n, 100)
    tens, ones = divmod(remainder, 10)
    parts: list[str] = []

    if hundreds > 0 or not is_leading_group:
        parts.append(f"{_ONES[hundreds]} trăm")

    if tens == 0:
        if ones > 0:
            parts.append(f"linh {_ONES[ones]}" if parts else _ONES[ones])
    elif tens == 1:
        parts.append("mười" if ones == 0 else f"mười {'lăm' if ones == 5 else _ONES[ones]}")
    else:
        tens_word = f"{_ONES[tens]} mươi"
        if ones == 0:
            parts.append(tens_word)
        elif ones == 1:
            parts.append(f"{tens_word} mốt")
        elif ones == 4:
            parts.append(f"{tens_word} tư")
        elif ones == 5:
            parts.append(f"{tens_word} lăm")
        else:
            parts.append(f"{tens_word} {_ONES[ones]}")

    return " ".join(parts)


def number_to_vietnamese_words(n: int) -> str:
    """0 <= |n| <= 999,999,999. Số ngoài phạm vi trả nguyên dạng chữ số
    (an toàn hơn là đọc sai) — xem `format_for_speech` nơi gọi hàm này."""
    if n == 0:
        return "không"
    if n < 0:
        return f"âm {number_to_vietnamese_words(-n)}"
    if n > 999_999_999:
        return str(n)

    groups: list[int] = []
    remainder = n
    while remainder > 0:
        groups.append(remainder % 1000)
        remainder //= 1000

    parts: list[str] = []
    for index in reversed(range(len(groups))):
        group_value = groups[index]
        if group_value == 0:
            continue
        is_leading_group = index == len(groups) - 1
        group_words = _read_three_digits(group_value, is_leading_group=is_leading_group)
        scale = _SCALE_WORDS[index] if index < len(_SCALE_WORDS) else ""
        parts.append(f"{group_words} {scale}".strip())
    return " ".join(parts)


def _read_decimal_digits(digits: str) -> str:
    return " ".join(_ONES[int(d)] for d in digits)


def format_for_speech(text: str) -> str:
    """Thay số dạng chữ số trong `text` bằng chữ đọc tự nhiên. An toàn với
    text không chứa số (trả nguyên văn)."""
    if not text:
        return text

    def _replace_decimal(match: re.Match[str]) -> str:
        integer_part, decimal_part = match.group(1), match.group(2)
        return f"{number_to_vietnamese_words(int(integer_part))} phẩy {_read_decimal_digits(decimal_part)}"

    result = _DECIMAL_RE.sub(_replace_decimal, text)

    def _replace_integer(match: re.Match[str]) -> str:
        value = int(match.group(0).replace(".", ""))
        return number_to_vietnamese_words(value)

    result = _INTEGER_RE.sub(_replace_integer, result)
    return _replace_currency_symbol(result)


# ---------------------------------------------------------------------------
# Dọn ký tự hay bị TTS đọc thành chữ theo nghĩa đen — phát hiện qua phản hồi
# thật khi nghe app (xem docs/voice-ai/mustdo_voice.md): dấu ngoặc kép dùng để nhấn
# mạnh 1 từ trong câu backend (vd `"Đúng"`, `“Thôi”`) và dấu gạch chéo ghép 2
# cách xưng hô (`Anh/chị`) đều KHÔNG phải dấu câu bình thường mà TTS quen xử
# lý im lặng — Edge-TTS đọc luôn ký tự đó ra thành lời thay vì bỏ qua.
# ---------------------------------------------------------------------------

_QUOTE_CHARS_RE = re.compile(r'["\'“”‘’]')  # " ' “ ” ‘ ’
_CURRENCY_SYMBOL_RE = re.compile(r"\s*₫")
_WHITESPACE_RE = re.compile(r"\s+")


def _replace_currency_symbol(text: str) -> str:
    # "85.000 ₫" (đã đổi số ở bước trên) -> "... nghìn đồng" thay vì đọc ký hiệu ₫
    # theo nghĩa đen (không phải chữ, TTS không biết đọc là gì).
    return _CURRENCY_SYMBOL_RE.sub(" đồng", text)


def sanitize_for_speech(text: str) -> str:
    """Loại bỏ dấu ngoặc kép (thẳng lẫn cong) và đổi dấu gạch chéo thành
    khoảng trắng trước khi đưa vào TTS — cả hai đều từng bị Edge-TTS đọc
    thành lời theo nghĩa đen thay vì coi là dấu câu/cách trình bày im lặng.
    An toàn với text không có các ký tự này (trả nguyên văn).
    """
    if not text:
        return text
    text = _QUOTE_CHARS_RE.sub("", text)
    text = text.replace("/", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()
