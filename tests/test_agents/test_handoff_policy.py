import pytest

from src.agents.agent import LLMAgent
from src.agents.contracts.schemas import ActionType, AgentInput
from src.agents.contracts.state import AgentState
from src.agents.core.handoff import HandoffReason, classify_handoff
from src.agents.core.model import ModelDecision


class ShouldNotRunModel:
    def __init__(self) -> None:
        self.called = False

    async def decide(self, **_kwargs):
        self.called = True
        return ModelDecision(message="không được gọi")


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Tôi vừa bị tai nạn, cần cấp cứu", HandoffReason.EMERGENCY),
        ("Tài xế lái xe nguy hiểm", HandoffReason.SAFETY_RISK),
        ("Tôi bị trừ tiền sai", HandoffReason.PAYMENT_DISPUTE),
        ("Tôi để quên đồ trên xe", HandoffReason.LOST_ITEM),
        ("Cho tôi gặp tổng đài viên", HandoffReason.USER_REQUEST),
    ],
)
def test_classify_specialized_handoff_cases(transcript, expected):
    assert classify_handoff(transcript) is expected


@pytest.mark.asyncio
async def test_emergency_handoff_bypasses_model_and_has_priority_context():
    model = ShouldNotRunModel()
    agent = LLMAgent(conversation_model=model)
    state = AgentState(session_id="session-emergency")

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-1",
            transcript="Tôi đang bị đe dọa và không an toàn",
        ),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    assert model.called is False
    context = action.state_updates["collected_data"]["handoff"]
    assert context["reason_code"] == "EMERGENCY"
    assert context["priority"] == 100
    assert context["severity"] == "CRITICAL"
    assert context["requires_immediate_transfer"] is True


@pytest.mark.asyncio
async def test_plain_booking_request_does_not_trigger_deterministic_handoff():
    model = ShouldNotRunModel()
    agent = LLMAgent(conversation_model=model)
    state = AgentState(session_id="session-booking")

    await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-1",
            transcript="Tôi muốn đặt xe đến sân bay",
        ),
        state,
    )

    assert model.called is True
