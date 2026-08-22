from collections.abc import AsyncIterable

import pytest

from src.voice_agent.tts_text import (
    format_vietnamese_currency,
    vietnamese_currency_tts_transform,
)


def test_format_vietnamese_currency_reads_grouped_and_plain_amounts() -> None:
    assert format_vietnamese_currency("giá 32000 đồng") == "giá ba mươi hai nghìn đồng"
    assert format_vietnamese_currency("giá 15 250 đồng") == ("giá mười lăm nghìn hai trăm năm mươi đồng")
    assert format_vietnamese_currency("giá 15.250 VND") == ("giá mười lăm nghìn hai trăm năm mươi đồng")


def test_format_vietnamese_currency_does_not_change_eta_or_place_numbers() -> None:
    text = "Xe 4 chỗ đến Landmark 81 sau 12 phút"
    assert format_vietnamese_currency(text) == text


@pytest.mark.asyncio
async def test_currency_transform_handles_amount_split_across_chunks() -> None:
    async def chunks() -> AsyncIterable[str]:
        for chunk in ("Giá dự kiến 15", ".2", "50 đ", "ồng, tới sau 12 phút."):
            yield chunk

    result = "".join([chunk async for chunk in vietnamese_currency_tts_transform(chunks())])

    assert result == "Giá dự kiến mười lăm nghìn hai trăm năm mươi đồng, tới sau 12 phút."
