import pytest

from src.agents.agent import LLMAgent
from src.agents.core.booking import BookingData, BookingStep
from src.agents.graph import AgentGraphAdapter
from src.agents.history import build_message_id
from src.agents.legacy.understanding.models import (
    ConfirmationIntent,
    Correction,
    CorrectionField,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.agents.legacy.understanding.rewrite_models import (
    ResolvedReference,
    RewriteResult,
)
from src.agents.schemas import ActionType, AgentInput, ToolName, ToolResult, ToolStatus
from src.agents.state import (
    AgentState,
    ConfirmationStatus,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)


class RecordingRewriter:
    def __init__(self, result: RewriteResult) -> None:
        self.result = result
        self.calls = []

    async def rewrite(self, original_text, context, decision):
        self.calls.append((original_text, context, decision))
        return self.result


class RecordingUnderstanding:
    def __init__(self, result: UnderstandingResult | None = None) -> None:
        self.result = result or UnderstandingResult()
        self.calls = []

    async def understand(self, transcript, context):
        self.calls.append((transcript, context))
        return self.result


def delivered_assistant(turn_id: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.ASSISTANT),
        turn_id=turn_id,
        role=ConversationRole.ASSISTANT,
        message_type=ConversationMessageType.ASSISTANT_SPEECH,
        content=content,
        delivery_status=DeliveryStatus.DELIVERED,
        spoken_content=content,
    )


def candidate_state() -> AgentState:
    data = BookingData(
        pickup_candidates=[
            {
                "place_id": "pickup-1",
                "display_name": "Hồ Gươm",
            },
            {
                "place_id": "pickup-2",
                "display_name": "Phố đi bộ Hồ Gươm",
            },
        ]
    )
    return AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step=BookingStep.SELECT_PICKUP_CANDIDATE.value,
        collected_data={"booking": data.model_dump(mode="json")},
        conversation_history=[
            delivered_assistant(
                "turn-001",
                "Tôi tìm thấy 1. Hồ Gươm và 2. Phố đi bộ Hồ Gươm. Bạn chọn địa điểm nào?",
            )
        ],
    )


def candidate_rewrite() -> RewriteResult:
    return RewriteResult(
        original_text="Cái thứ hai",
        rewritten_text="Người dùng chọn Phố đi bộ Hồ Gươm làm điểm đón.",
        changed=True,
        confidence=0.96,
        resolved_references=[
            ResolvedReference(
                original_phrase="Cái thứ hai",
                resolved_value="Phố đi bộ Hồ Gươm",
                source_turn_id="turn-001",
            )
        ],
    )


@pytest.mark.asyncio
async def test_contextual_rewrite_drives_candidate_selection_but_history_keeps_raw():
    rewriter = RecordingRewriter(candidate_rewrite())
    understanding = RecordingUnderstanding()
    agent = LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Cái thứ hai",
        ),
        candidate_state(),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.COLLECT_DESTINATION.value
    booking = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert booking.pickup is not None
    assert booking.pickup.place_id == "pickup-2"
    assert len(rewriter.calls) == 1
    assert understanding.calls[0][0] == candidate_rewrite().rewritten_text
    understanding_context = understanding.calls[0][1]
    assert understanding_context.rewrite_applied is True
    assert understanding_context.rewrite_evidence[0].source_turn_id == "turn-001"
    assert len(understanding_context.available_candidates) == 2

    user_messages = [
        message
        for message in action.state_updates["conversation_history"]
        if message.message_type is ConversationMessageType.USER_TRANSCRIPT
    ]
    assert user_messages[-1].content == "Cái thứ hai"
    assert candidate_rewrite().rewritten_text not in [message.content for message in user_messages]


@pytest.mark.asyncio
async def test_graph_chat_uses_contextual_rewrite_when_backend_supplies_state():
    graph = AgentGraphAdapter(
        LLMAgent(
            message_rewriter=RecordingRewriter(candidate_rewrite()),
            understanding_service=RecordingUnderstanding(),
        )
    )

    result = await graph.ainvoke(
        {
            "session_id": "session-001",
            "turn_id": "turn-002",
            "query": "Cái thứ hai",
            "state": candidate_state().model_dump(mode="json"),
        }
    )

    action = result["action"]
    assert action["action_type"] == ActionType.ASK_USER.value
    assert action["state_updates"]["current_step"] == BookingStep.COLLECT_DESTINATION.value
    booking = BookingData.model_validate(action["state_updates"]["collected_data"]["booking"])
    assert booking.pickup is not None
    assert booking.pickup.place_id == "pickup-2"


@pytest.mark.asyncio
async def test_gate_fast_path_skips_rewriter_and_understanding_receives_raw():
    rewriter = RecordingRewriter(candidate_rewrite())
    understanding = RecordingUnderstanding(
        UnderstandingResult(
            intent=UnderstandingIntent.RIDE_BOOKING,
            confidence=0.9,
        )
    )
    agent = LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    )

    await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi muốn đặt xe",
        )
    )

    assert rewriter.calls == []
    assert understanding.calls[0][0] == "Tôi muốn đặt xe"
    assert understanding.calls[0][1].rewrite_applied is False


@pytest.mark.asyncio
async def test_rewrite_fallback_continues_workflow_with_raw_text():
    rewriter = RecordingRewriter(
        RewriteResult.unchanged(
            "Cái thứ hai",
            ambiguity="rewrite_provider_error",
        )
    )
    understanding = RecordingUnderstanding()
    agent = LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Cái thứ hai",
        ),
        candidate_state(),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == BookingStep.SELECT_PICKUP_CANDIDATE.value
    assert understanding.calls[0][0] == "Cái thứ hai"
    assert understanding.calls[0][1].rewrite_ambiguities == ["rewrite_provider_error"]


@pytest.mark.asyncio
async def test_tool_result_turn_skips_rewriter_and_understanding():
    rewriter = RecordingRewriter(candidate_rewrite())
    understanding = RecordingUnderstanding()
    agent = LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    )
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step=BookingStep.WAITING_FOR_PICKUP_RESULT.value,
        pending_tool_call_id="call-001",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="call-001",
                status=ToolStatus.SUCCESS,
                data={"candidates": []},
            ),
        ),
        state,
    )

    assert rewriter.calls == []
    assert understanding.calls == []


@pytest.mark.asyncio
async def test_emergency_turn_skips_rewriter_and_understanding():
    rewriter = RecordingRewriter(candidate_rewrite())
    understanding = RecordingUnderstanding()
    action = await LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    ).handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi đang gặp nguy hiểm",
        )
    )

    assert action.action_type is ActionType.HANDOFF
    assert rewriter.calls == []
    assert understanding.calls == []


@pytest.mark.asyncio
async def test_understanding_confirmation_without_raw_evidence_is_downgraded():
    raw_text = "Cái đó"
    rewriter = RecordingRewriter(
        RewriteResult(
            original_text=raw_text,
            rewritten_text=("Người dùng chọn Times City và xác nhận đặt xe đi."),
            changed=True,
            confidence=0.99,
            resolved_references=[
                ResolvedReference(
                    original_phrase=raw_text,
                    resolved_value="Times City",
                    source_turn_id="turn-001",
                )
            ],
        )
    )
    understanding = RecordingUnderstanding(
        UnderstandingResult(
            confirmation=ConfirmationIntent.CONFIRM,
            confidence=0.99,
        )
    )
    booking = BookingData(
        pickup={"place_id": "pickup-1", "display_name": "Hồ Gươm"},
        destination={"place_id": "destination-1", "display_name": "Times City"},
        phone_number="0901234567",
    )
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step=BookingStep.CONFIRM.value,
        collected_data={"booking": booking.model_dump(mode="json")},
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        conversation_history=[
            delivered_assistant(
                "turn-001",
                "Bạn xác nhận đặt xe từ Hồ Gươm đến Times City, đúng không?",
            )
        ],
    )

    action = await LLMAgent(
        message_rewriter=rewriter,
        understanding_service=understanding,
    ).handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript=raw_text,
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.tool_call is None
    assert action.state_updates["confirmation"] is ConfirmationStatus.AWAITING_CONFIRMATION


def test_raw_evidence_safety_removes_hallucinated_identity_fields():
    from src.agents.legacy.understanding.safety import enforce_raw_understanding_evidence

    result = enforce_raw_understanding_evidence(
        UnderstandingResult(
            phone_number="0901234567",
            booking_id="GSM-12345",
        ),
        raw_transcript="Cho tôi tra cứu chuyến lúc nãy",
    )

    assert result.phone_number is None
    assert result.booking_id is None


def test_raw_evidence_safety_keeps_matching_identity_and_rejects_negated_confirmation():
    from src.agents.legacy.understanding.safety import enforce_raw_understanding_evidence

    result = enforce_raw_understanding_evidence(
        UnderstandingResult(
            phone_number="+84901234567",
            booking_id="GSM-12345",
            confirmation=ConfirmationIntent.CONFIRM,
        ),
        raw_transcript="Không đúng, số 0901234567 và mã GSM-12345",
    )

    assert result.phone_number == "+84901234567"
    assert result.booking_id == "GSM-12345"
    assert result.confirmation is ConfirmationIntent.UNCLEAR


def test_raw_evidence_safety_removes_ungrounded_corrections():
    from src.agents.legacy.understanding.safety import enforce_raw_understanding_evidence

    result = enforce_raw_understanding_evidence(
        UnderstandingResult(
            corrections=[
                Correction(
                    field=CorrectionField.DESTINATION,
                    value="Royal City",
                ),
                Correction(
                    field=CorrectionField.PHONE_NUMBER,
                    value="0901234567",
                ),
            ]
        ),
        raw_transcript="Sửa điểm đến giúp tôi",
    )

    assert result.corrections == []
