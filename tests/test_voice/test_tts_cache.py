import pytest

from src.voice.tts.cache import STATIC_PHRASES, CachingTTSProvider
from tests.test_voice.fake_providers import FakeTTSProvider


@pytest.mark.asyncio
async def test_synthesize_calls_inner_once_per_unique_text():
    inner = FakeTTSProvider()
    cache = CachingTTSProvider(inner)

    await cache.synthesize("xin chào")
    await cache.synthesize("xin chào")
    await cache.synthesize("tạm biệt")

    assert inner.calls == ["xin chào", "tạm biệt"]
    assert cache.cache_size() == 2


@pytest.mark.asyncio
async def test_returns_same_result_object_on_cache_hit():
    inner = FakeTTSProvider()
    cache = CachingTTSProvider(inner)

    first = await cache.synthesize("xin chào")
    second = await cache.synthesize("xin chào")

    assert first.audio == second.audio


@pytest.mark.asyncio
async def test_cache_key_includes_voice():
    inner = FakeTTSProvider()
    cache = CachingTTSProvider(inner)

    await cache.synthesize("xin chào", voice="a")
    await cache.synthesize("xin chào", voice="b")

    assert len(inner.calls) == 2
    assert cache.cache_size() == 2


@pytest.mark.asyncio
async def test_prewarm_populates_cache_for_default_static_phrases():
    inner = FakeTTSProvider()
    cache = CachingTTSProvider(inner)

    await cache.prewarm()

    assert cache.cache_size() == len(STATIC_PHRASES)
    assert set(inner.calls) == set(STATIC_PHRASES)


@pytest.mark.asyncio
async def test_prewarm_with_custom_phrase_list():
    inner = FakeTTSProvider()
    cache = CachingTTSProvider(inner)

    await cache.prewarm(["câu riêng 1", "câu riêng 2"])

    assert cache.cache_size() == 2
    assert inner.calls == ["câu riêng 1", "câu riêng 2"]
