from __future__ import annotations

import pytest

from src.backend.config import Settings
from src.backend.integrations.voice_client import NoSpeechDetectedError
from src.backend.services.voice_service import VoiceService
from src.voice.text.rewrite_contract import TranscriptRewriteResult


class _SessionService:
    def get_session(self, session_id: str) -> dict[str, object]:
        return {"session_id": session_id}

    async def process_message(self, *args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("ASR silence/hallucination must not reach the agent")


class _IdentityRewriter:
    async def rewrite(self, text: str, **_: object) -> TranscriptRewriteResult:
        return TranscriptRewriteResult(raw_text=text, normalized_text=text, reason="unchanged")


class _NoSpeechClient:
    async def transcribe(self, *args: object, **kwargs: object) -> str:
        raise NoSpeechDetectedError("Không nhận diện được giọng nói")


class _HallucinationClient:
    async def transcribe(self, *args: object, **kwargs: object) -> str:
        return "Hẹn gặp lại các bạn trong những video tiếp theo nhé!"


class _AliasClient:
    async def transcribe(self, *args: object, **kwargs: object) -> str:
        return "Đón tôi ở Bình Yuni rồi đi Hồ Cương"


class _CapturingSessionService:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def get_session(self, session_id: str) -> dict[str, object]:
        return {"session_id": session_id}

    async def process_message(self, session_id: str, message: str, *args: object, **kwargs: object) -> dict[str, object]:
        self.messages.append(message)
        return {"message_id": "msg_test", "action": "ASK_USER", "message": "Bạn muốn đi xe gì?", "state": {}}


class _TtsResult:
    audio = b"audio"
    provider = "test"
    voice = "test"
    fallback_used = False
    duration_ms = 0
    mime_type = "audio/mpeg"
    review_decision = "allow"
    review_reason_codes: list[str] = []


class _Tts:
    async def synthesize(self, *args: object, **kwargs: object) -> _TtsResult:
        return _TtsResult()


def _service() -> VoiceService:
    return VoiceService(
        session_service=_SessionService(),
        settings=Settings(_env_file=None),
        transcript_rewriter=_IdentityRewriter(),
    )


@pytest.mark.asyncio
async def test_no_speech_returns_reprompt_instead_of_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.backend.services.voice_service.resolve_voice_provider", lambda _: "zipformer")
    monkeypatch.setattr("src.backend.services.voice_service.build_voice_client", lambda _: _NoSpeechClient())

    result = await _service().process_turn("sess_test", b"audio")

    assert result["action"] == "ASK_USER"
    assert result["transcript"] == ""
    assert result["transcript_rewrite_reason"] == "no_speech_detected"
    assert result["message_id"]


@pytest.mark.asyncio
async def test_known_asr_hallucination_is_blocked_before_rewrite_or_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.backend.services.voice_service.resolve_voice_provider", lambda _: "zipformer")
    monkeypatch.setattr("src.backend.services.voice_service.build_voice_client", lambda _: _HallucinationClient())

    result = await _service().process_turn("sess_test", b"audio")

    assert result["action"] == "ASK_USER"
    assert result["transcript"] == ""
    assert result["transcript_rewrite_reason"] == "known_asr_hallucination"
    assert result["message_id"]


@pytest.mark.asyncio
async def test_known_place_alias_is_corrected_before_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    session_service = _CapturingSessionService()
    service = VoiceService(
        session_service=session_service,
        settings=Settings(_env_file=None),
        transcript_rewriter=_IdentityRewriter(),
    )
    monkeypatch.setattr("src.backend.services.voice_service.resolve_voice_provider", lambda _: "zipformer")
    monkeypatch.setattr("src.backend.services.voice_service.build_voice_client", lambda _: _AliasClient())
    monkeypatch.setattr("src.backend.services.voice_service.get_tts_orchestrator", lambda: _Tts())

    result = await service.process_turn("sess_test", b"audio")

    assert session_service.messages == ["Đón tôi ở VinUni rồi đi Hồ Gươm"]
    assert result["transcript_rewritten"] is True
    assert result["transcript_rewrite_reason"] == "alias_catalog_applied"
    assert result["transcript_rewrite"]["provider"] == "alias_catalog"
