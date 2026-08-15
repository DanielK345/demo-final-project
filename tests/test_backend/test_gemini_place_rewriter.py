import pytest

from src.agents.schemas import ActionType, AgentAction
from src.backend.services.gemini_place_rewriter import TranscriptRewriteResult
from src.backend.services.session_service import SessionService


class _StubRewriter:
    async def rewrite(self, transcript: str, *, source: str) -> TranscriptRewriteResult:
        assert source == "VOICE"
        return TranscriptRewriteResult(
            original=transcript,
            rewritten=transcript.replace("Bình Yuni", "VinUni").replace("Hồ Cương", "Hồ Gươm"),
            applied=True,
            provider="gemini",
        )


class _CapturingAgent:
    def __init__(self) -> None:
        self.transcripts: list[str] = []

    async def handle(self, agent_input, state):
        self.transcripts.append(agent_input.transcript)
        return AgentAction(
            action_type=ActionType.ASK_USER,
            message="Bạn muốn đón ở đâu?",
        )


@pytest.mark.asyncio
async def test_voice_transcript_is_rewritten_before_agent(monkeypatch):
    SessionService.sessions.clear()
    agent = _CapturingAgent()
    monkeypatch.setattr(SessionService, "_agent", agent)
    monkeypatch.setattr(SessionService, "_transcript_rewriter", _StubRewriter())
    service = SessionService()
    session_id = service.create_session("usr_test", "WEB_VOICE")["session_id"]

    await service.process_message(str(session_id), "Đón tôi ở Bình Yuni rồi đi Hồ Cương", source="VOICE")

    assert agent.transcripts == ["Đón tôi ở VinUni rồi đi Hồ Gươm"]
