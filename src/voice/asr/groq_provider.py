"""Groq Whisper ASR provider — Phần 3, D1 (`docs/voice-ai/voice_ai_overview.md`).

CHƯA test với `GROQ_API_KEY` thật trong môi trường build code này — xem
`docs/voice-ai/mustdo_voice.md`. Implement theo tài liệu công khai của Groq
(endpoint OpenAI-compatible `/audio/transcriptions`,
https://console.groq.com/docs/speech-to-text, model `whisper-large-v3-turbo`).

Không dùng SDK `groq` (tránh thêm dependency) — gọi thẳng qua `httpx`, vốn
đã có sẵn trong `requirements.txt`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import wave

import httpx

from src.voice.schemas import ASRResult

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_PROMPT_CHARS = 800  # Groq/Whisper prompt có giới hạn token — cắt bớt cho an toàn


def _pcm16_to_wav_bytes(pcm16: bytes, sample_rate: int) -> bytes:
    """Groq API cần audio có container (wav/mp3/...) — không nhận PCM thô."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # PCM16 = 2 bytes/sample
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16)
    return buffer.getvalue()


def estimate_confidence(payload: dict) -> float:
    """Groq/Whisper `verbose_json` không trả field "confidence" trực tiếp —
    ước lượng từ `segments[].avg_logprob` (thường trong khoảng [-1, 0]) và
    `no_speech_prob`.

    Đây là heuristic, không phải xác suất chuẩn — cần hiệu chỉnh bằng test
    tay với audio thật (Tuần 5, `docs/voice-ai/voice_ai_overview.md` §8) trước khi
    dùng để quyết định BR-001 trong môi trường thật.
    """
    segments = payload.get("segments") or []
    if not segments:
        return 0.5  # không có segment info -> confidence trung tính, không đoán cao/thấp
    no_speech = [float(s.get("no_speech_prob", 0.0)) for s in segments]
    avg_logprob = [float(s.get("avg_logprob", -1.0)) for s in segments]
    speech_conf = 1.0 - (sum(no_speech) / len(no_speech))
    logprob_conf = (sum(avg_logprob) / len(avg_logprob)) + 1.0  # xấp xỉ [-1,0] -> [0,1]
    combined = (speech_conf + logprob_conf) / 2.0
    return max(0.0, min(1.0, combined))


# Câu Whisper hay "bịa" ra khi audio thực chất gần như im lặng/không có tiếng nói
# thật — quan sát được khi test tay với GROQ_API_KEY thật (docs/voice-ai/mustdo_voice.md).
# `estimate_confidence()` KHÔNG bắt được case này (no_speech_prob=0, avg_logprob
# cao — Whisper "tự tin" với chính câu nó bịa ra). Danh sách này không đầy đủ, chỉ
# chặn các case đã tự gặp — mở rộng khi phát hiện thêm câu hallucination khác.
_KNOWN_HALLUCINATION_PHRASES = {
    "hãy subscribe cho kênh ghiền mì gõ để không bỏ lỡ những video hấp dẫn",
    "cảm ơn các bạn đã theo dõi",
    "đăng ký kênh để không bỏ lỡ những video hấp dẫn",
    "hãy subscribe cho kênh để không bỏ lỡ những video hấp dẫn",
    "hẹn gặp lại các bạn trong những video tiếp theo nhé",
    "hẹn gặp lại các bạn trong những video tiếp theo",
}


def is_known_hallucination(text: str) -> bool:
    return text.strip().lower().rstrip(".!?") in _KNOWN_HALLUCINATION_PHRASES


class GroqASRProvider:
    """Implement `ASRProvider` (`voice/asr/base.py`) bằng Groq Whisper API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "whisper-large-v3-turbo",
        timeout: float = 15.0,
        max_retries: int = 1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "GroqASRProvider cần GROQ_API_KEY (xem docs/voice-ai/mustdo_voice.md, mục ASR/TTS provider)."
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = client  # inject httpx.AsyncClient giả trong test — không gọi mạng thật

    async def transcribe(
        self,
        pcm16_audio: bytes,
        *,
        sample_rate: int = 16000,
        language: str = "vi",
        prompt_hint: str = "",
    ) -> ASRResult:
        if not pcm16_audio:
            return ASRResult(text="", confidence=0.0, duration_ms=0, language=language)

        wav_bytes = _pcm16_to_wav_bytes(pcm16_audio, sample_rate)
        data = {"model": self._model, "language": language, "response_format": "verbose_json"}
        if prompt_hint:
            data["prompt"] = prompt_hint[:_MAX_PROMPT_CHARS]
        headers = {"Authorization": f"Bearer {self._api_key}"}

        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self._timeout)

        start = time.monotonic()
        try:
            payload = await self._post_with_retry(client, data, headers, wav_bytes)
        finally:
            if owns_client:
                await client.aclose()
        duration_ms = int((time.monotonic() - start) * 1000)

        text = (payload.get("text") or "").strip()
        is_hallucination = is_known_hallucination(text)
        confidence = 0.0 if is_hallucination else estimate_confidence(payload)
        return ASRResult(
            # Empty text routes the gateway to its reprompt branch. Merely
            # lowering confidence would incorrectly send the hallucination to
            # the Agent and can trigger a human handoff.
            text="" if is_hallucination else text,
            confidence=confidence,
            duration_ms=duration_ms,
            language=language,
            raw=payload,
        )

    async def _post_with_retry(
        self,
        client: httpx.AsyncClient,
        data: dict,
        headers: dict,
        wav_bytes: bytes,
    ) -> dict:
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
            try:
                response = await client.post(GROQ_TRANSCRIPTIONS_URL, headers=headers, data=data, files=files)
            except httpx.TimeoutException as exc:
                last_exc = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response.json()
                last_exc = httpx.HTTPStatusError(
                    f"Groq trả HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            attempt += 1
            if attempt <= self._max_retries:
                logger.warning("Groq ASR request thất bại (lần %s), thử lại: %s", attempt, last_exc)
                await asyncio.sleep(0.5 * attempt)

        assert last_exc is not None
        raise last_exc
