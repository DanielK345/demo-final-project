"""LiveKit TTS text transforms for Vietnamese booking speech."""

from __future__ import annotations

import re
from collections.abc import AsyncIterable

_ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_SCALE_WORDS = ["", "nghìn", "triệu", "tỷ"]


def _read_three_digits(number: int, *, is_leading_group: bool) -> str:
    if number == 0:
        return "" if is_leading_group else "không trăm"

    hundreds, remainder = divmod(number, 100)
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
        suffix = {0: "", 1: " mốt", 4: " tư", 5: " lăm"}.get(ones, f" {_ONES[ones]}")
        parts.append(f"{tens_word}{suffix}")

    return " ".join(parts)


def number_to_vietnamese_words(number: int) -> str:
    """Convert fare-sized integers to Vietnamese words for LiveKit TTS."""

    if number == 0:
        return "không"
    if number < 0:
        return f"âm {number_to_vietnamese_words(-number)}"
    if number > 999_999_999:
        return str(number)

    groups: list[int] = []
    remainder = number
    while remainder:
        groups.append(remainder % 1000)
        remainder //= 1000

    parts: list[str] = []
    for index in reversed(range(len(groups))):
        if groups[index] == 0:
            continue
        words = _read_three_digits(groups[index], is_leading_group=index == len(groups) - 1)
        parts.append(f"{words} {_SCALE_WORDS[index]}".strip())
    return " ".join(parts)

_CURRENCY_RE = re.compile(
    r"(?<!\d)(\d(?:[\d .,_]*\d)?)\s*(?:(?:VND|đồng)\b|₫)",
    flags=re.IGNORECASE,
)
# Keep only a trailing number/currency prefix between streamed LLM chunks. This
# lets the rest of the response continue to TTS without waiting for completion.
_PENDING_CURRENCY_RE = re.compile(
    r"(?<!\d)\d[\d .,_]*(?:\s*(?:đ(?:ồ(?:n(?:g)?)?)?|V(?:N(?:D)?)?|₫)?)?$",
    flags=re.IGNORECASE,
)


def format_vietnamese_currency(text: str) -> str:
    """Render integer VND amounts as words while leaving other numbers alone."""

    def replace(match: re.Match[str]) -> str:
        digits = re.sub(r"[ .,_]", "", match.group(1))
        return f"{number_to_vietnamese_words(int(digits))} đồng"

    return _CURRENCY_RE.sub(replace, text)


async def vietnamese_currency_tts_transform(text: AsyncIterable[str]) -> AsyncIterable[str]:
    """Streaming-safe LiveKit transform for amounts split across LLM chunks."""

    buffer = ""
    async for chunk in text:
        buffer = format_vietnamese_currency(buffer + chunk)
        pending = _PENDING_CURRENCY_RE.search(buffer)
        flush_to = pending.start() if pending else len(buffer)
        if flush_to:
            yield buffer[:flush_to]
            buffer = buffer[flush_to:]

    if buffer:
        yield format_vietnamese_currency(buffer)
