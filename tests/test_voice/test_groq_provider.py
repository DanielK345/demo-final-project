"""Test `GroqASRProvider` — không gọi Groq thật (dùng `httpx.MockTransport`,
đúng nguyên tắc test-double). Xem `docs/mustdo_voice.md` cho việc test tay
với `GROQ_API_KEY` thật — bao gồm 1 bug thật đã phát hiện: Whisper "bịa" câu
hoàn chỉnh với confidence cao khi audio gần như im lặng (test regression cho
case này nằm trong `test_transcribe_forces_zero_confidence_for_known_hallucination`
bên dưới)."""

import httpx
import pytest

from src.voice.asr.groq_provider import (
    GROQ_TRANSCRIPTIONS_URL,
    GroqASRProvider,
    estimate_confidence,
    is_known_hallucination,
)


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        GroqASRProvider("")


@pytest.mark.asyncio
async def test_empty_audio_returns_immediately_without_network():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - không nên chạy
        raise AssertionError("không nên gọi network khi audio rỗng")

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler))
    result = await provider.transcribe(b"")
    assert result.text == ""
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_transcribe_success_parses_text_and_confidence():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(GROQ_TRANSCRIPTIONS_URL)
        assert request.headers["Authorization"] == "Bearer fake-key"
        return httpx.Response(
            200,
            json={
                "text": "cho tôi đi landmark 81",
                "segments": [{"avg_logprob": -0.2, "no_speech_prob": 0.02}],
            },
        )

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler))
    result = await provider.transcribe(b"\x00\x00" * 1600, sample_rate=16000)
    assert result.text == "cho tôi đi landmark 81"
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence > 0.7  # segment tốt -> confidence cao


@pytest.mark.asyncio
async def test_prompt_hint_is_sent_and_truncated():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # multipart/form-data body -> kiểm tra prompt có mặt trong raw content thay vì parse form
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "ok", "segments": []})

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler))
    await provider.transcribe(b"\x00\x00" * 100, prompt_hint="A" * 2000)
    assert b"A" * 800 in seen["body"]
    assert b"A" * 801 not in seen["body"]


@pytest.mark.asyncio
async def test_retries_once_on_429_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"text": "ok", "segments": []})

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler), max_retries=1)
    result = await provider.transcribe(b"\x00\x00" * 100)
    assert result.text == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_raises_after_exhausting_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler), max_retries=1)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.transcribe(b"\x00\x00" * 100)


@pytest.mark.asyncio
async def test_non_retryable_error_raises_immediately():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler), max_retries=2)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.transcribe(b"\x00\x00" * 100)
    assert calls["count"] == 1


def test_estimate_confidence_no_segments_is_neutral():
    assert estimate_confidence({}) == 0.5


def test_estimate_confidence_high_when_speech_likely():
    payload = {"segments": [{"avg_logprob": -0.1, "no_speech_prob": 0.01}]}
    assert estimate_confidence(payload) > 0.8


def test_estimate_confidence_low_when_no_speech_likely():
    payload = {"segments": [{"avg_logprob": -1.0, "no_speech_prob": 0.9}]}
    assert estimate_confidence(payload) < 0.3


def test_is_known_hallucination_matches_case_and_punctuation_insensitively():
    assert is_known_hallucination("Hãy subscribe cho kênh Ghiền Mì Gõ để không bỏ lỡ những video hấp dẫn.")
    assert is_known_hallucination("HÃY SUBSCRIBE CHO KÊNH GHIỀN MÌ GÕ ĐỂ KHÔNG BỎ LỠ NHỮNG VIDEO HẤP DẪN")


def test_is_known_hallucination_false_for_real_text():
    assert not is_known_hallucination("Tôi muốn đặt xe từ Vincom Đồng Khởi đến Landmark 81")


@pytest.mark.asyncio
async def test_transcribe_forces_zero_confidence_for_known_hallucination():
    """Regression cho bug thật: audio gần như im lặng khiến Whisper bịa ra câu hoàn
    chỉnh với no_speech_prob=0/avg_logprob cao (tức estimate_confidence() sẽ tính ra
    CAO) — payload dưới đây tái hiện đúng response thật đã quan sát được khi test tay
    với GROQ_API_KEY thật (xem docs/mustdo_voice.md)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "text": " Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn",
                "segments": [{"avg_logprob": -0.08032052, "no_speech_prob": 0}],
            },
        )

    provider = GroqASRProvider("fake-key", client=_client_with_handler(handler))
    result = await provider.transcribe(b"\x00\x00" * 16000)

    # Nếu không có guard, estimate_confidence() sẽ tính ra >0.9 cho payload này.
    assert estimate_confidence(
        {"segments": [{"avg_logprob": -0.08032052, "no_speech_prob": 0}]}
    ) > 0.9
    assert result.confidence == 0.0
