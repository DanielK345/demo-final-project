"""Test `EdgeTTSProvider` — không gọi Edge-TTS thật (inject `communicate_factory`
giả, đúng nguyên tắc test-double). Đã tự verify tay bằng script riêng (không
commit vào test suite) rằng provider gọi được Edge-TTS thật trong môi trường
phát triển — xem `docs/voice-ai/mustdo_voice.md`."""

import pytest

from src.voice.tts.edge_tts_provider import EdgeTTSProvider, rate_to_edge_tts_param


class _FakeCommunicate:
    def __init__(self, text: str, voice: str, rate: str) -> None:
        self.text = text
        self.voice = voice
        self.rate = rate

    async def stream(self):
        yield {"type": "audio", "data": b"chunk1"}
        yield {"type": "WordBoundary", "text": "x", "offset": 0, "duration": 1}
        yield {"type": "audio", "data": b"chunk2"}


def test_rate_to_edge_tts_param_normal_speed():
    assert rate_to_edge_tts_param(1.0) == "+0%"


def test_rate_to_edge_tts_param_slower():
    assert rate_to_edge_tts_param(0.9) == "-10%"


def test_rate_to_edge_tts_param_faster():
    assert rate_to_edge_tts_param(1.1) == "+10%"


@pytest.mark.asyncio
async def test_synthesize_concatenates_audio_chunks_and_skips_boundaries():
    provider = EdgeTTSProvider(communicate_factory=_FakeCommunicate)
    result = await provider.synthesize("xin chào")
    assert result.audio == b"chunk1chunk2"
    assert result.mime_type == "audio/mpeg"
    assert result.text == "xin chào"
    assert result.sample_rate == 24000


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_empty_without_calling_factory():
    def boom(*args, **kwargs):  # pragma: no cover - không nên chạy
        raise AssertionError("không nên tạo Communicate khi text rỗng")

    provider = EdgeTTSProvider(communicate_factory=boom)
    result = await provider.synthesize("   ")
    assert result.audio == b""


@pytest.mark.asyncio
async def test_uses_default_voice_when_not_specified():
    captured = {}

    def factory(text: str, voice: str, *, rate: str) -> _FakeCommunicate:
        captured["voice"] = voice
        return _FakeCommunicate(text, voice, rate)

    provider = EdgeTTSProvider(default_voice="vi-VN-HoaiMyNeural", communicate_factory=factory)
    await provider.synthesize("hi")
    assert captured["voice"] == "vi-VN-HoaiMyNeural"


@pytest.mark.asyncio
async def test_voice_override_takes_precedence():
    captured = {}

    def factory(text: str, voice: str, *, rate: str) -> _FakeCommunicate:
        captured["voice"] = voice
        return _FakeCommunicate(text, voice, rate)

    provider = EdgeTTSProvider(default_voice="vi-VN-HoaiMyNeural", communicate_factory=factory)
    await provider.synthesize("hi", voice="en-US-EmmaMultilingualNeural")
    assert captured["voice"] == "en-US-EmmaMultilingualNeural"


@pytest.mark.asyncio
async def test_rate_param_passed_through_to_factory():
    captured = {}

    def factory(text: str, voice: str, *, rate: str) -> _FakeCommunicate:
        captured["rate"] = rate
        return _FakeCommunicate(text, voice, rate)

    provider = EdgeTTSProvider(rate=0.9, communicate_factory=factory)
    await provider.synthesize("hi")
    assert captured["rate"] == "-10%"
