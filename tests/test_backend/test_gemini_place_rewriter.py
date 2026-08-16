import pytest

from src.agents.schemas import ActionType, AgentAction
from src.backend.services.session_service import SessionService


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
async def test_session_service_does_not_apply_a_second_voice_rewrite(monkeypatch):
    SessionService.sessions.clear()
    agent = _CapturingAgent()
    monkeypatch.setattr(SessionService, "_agent", agent)
    service = SessionService()
    session_id = service.create_session("usr_test", "WEB_VOICE")["session_id"]

    response = await service.process_message(
        str(session_id), "Đón tôi ở Bình Yuni rồi đi Hồ Cương", source="VOICE"
    )

    assert agent.transcripts == ["Đón tôi ở Bình Yuni rồi đi Hồ Cương"]
    assert response["transcript"] == "Đón tôi ở Bình Yuni rồi đi Hồ Cương"
    assert response["transcript_rewrite"] == {
        "provider": "voice_layer",
        "called": False,
        "applied": False,
        "status": "handled_upstream",
    }
