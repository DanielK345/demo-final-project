"""LiveKit TTS text transforms for Vietnamese booking speech."""

from __future__ import annotations

import re
from collections.abc import AsyncIterable

from src.voice.tts.formatter import number_to_vietnamese_words

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
