from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from src.agents.agent import LLMAgent
from src.agents.schemas import ActionType, AgentInput, ToolName, ToolResult, ToolStatus
from src.agents.state import AgentState
from src.agents.understanding.base import UnderstandingProviderError
from src.agents.understanding.models import (
    ConfirmationIntent,
    Correction,
    CorrectionField,
    UnderstandingContext,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.agents.understanding.openai import OpenAIUnderstandingAdapter
from src.agents.understanding.rules import RuleBasedUnderstanding
from src.agents.understanding.service import ResilientUnderstandingService


class RecordingUnderstanding:
    def __init__(self, result: UnderstandingResult) -> None:
        self.result = result
        self.calls = []

    async def understand(self, transcript, context):
        self.calls.append((transcript, context))
        return self.result


class FailingUnderstanding:
    async def understand(self, transcript, context):
        del transcript, context
        raise UnderstandingProviderError("provider unavailable")


class FakeResponses:
    def __init__(self, parsed=None, error=None) -> None:
        self.parsed = parsed
        self.error = error
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


@pytest.mark.asyncio
async def test_agent_uses_structured_intent_for_natural_vietnamese_request():
    understanding = RecordingUnderstanding(
        UnderstandingResult(
            intent=UnderstandingIntent.RIDE_BOOKING,
            pickup_query="cổng Vinmec",
            destination_query="Times City",
            confidence=0.95,
        )
    )
    agent = LLMAgent(understanding_service=understanding)

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            transcript="Bác đang cạnh bệnh viện, gọi một cuốc về khu Times nhé",
        )
    )

    assert len(understanding.calls) == 1
    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert action.tool_call.params == {"query": "cổng Vinmec"}


@pytest.mark.asyncio
async def test_deterministic_emergency_skips_understanding_provider():
    understanding = RecordingUnderstanding(UnderstandingResult())
    agent = LLMAgent(understanding_service=understanding)

    action = await agent.handle(
        AgentInput(session_id="session-001", transcript="Tôi đang gặp nguy hiểm")
    )

    assert action.action_type is ActionType.HANDOFF
    context = action.state_updates["collected_data"]["handoff_context"]
    assert context["reason_code"] == "EMERGENCY"
    assert understanding.calls == []


@pytest.mark.asyncio
async def test_structured_handoff_overrides_active_business_workflow():
    understanding = RecordingUnderstanding(
        UnderstandingResult(
            intent=UnderstandingIntent.HUMAN_HANDOFF,
            handoff_reason="User requests human support",
            confidence=0.9,
        )
    )
    agent = LLMAgent(understanding_service=understanding)
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step="COLLECT_DESTINATION",
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            transcript="Tôi muốn nói chuyện trực tiếp với người hỗ trợ",
        ),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    context = action.state_updates["collected_data"]["handoff_context"]
    assert context["reason_code"] == "USER_REQUEST"


@pytest.mark.asyncio
async def test_tool_result_turn_does_not_call_understanding_provider():
    understanding = RecordingUnderstanding(UnderstandingResult())
    agent = LLMAgent(understanding_service=understanding)
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step="WAITING_FOR_PICKUP_RESULT",
        pending_tool_call_id="call-001",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    await agent.handle(
        AgentInput(
            session_id="session-001",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="call-001",
                status=ToolStatus.SUCCESS,
                data={"candidates": []},
            ),
        ),
        state,
    )

    assert understanding.calls == []


@pytest.mark.asyncio
async def test_structured_confirmation_cannot_bypass_incomplete_booking_state():
    understanding = RecordingUnderstanding(
        UnderstandingResult(confirmation=ConfirmationIntent.CONFIRM, confidence=0.9)
    )
    agent = LLMAgent(understanding_service=understanding)
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step="CONFIRM",
    )

    action = await agent.handle(
        AgentInput(session_id="session-001", transcript="Vâng bác đồng ý"),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.tool_call is None


@pytest.mark.asyncio
async def test_structured_correction_restarts_place_resolution():
    understanding = RecordingUnderstanding(
        UnderstandingResult(
            corrections=[
                Correction(
                    field=CorrectionField.DESTINATION,
                    value="Royal City",
                )
            ],
            confidence=0.9,
        )
    )
    agent = LLMAgent(understanding_service=understanding)
    state = AgentState(
        session_id="session-001",
        current_workflow="RIDE_BOOKING",
        current_step="CONFIRM",
        collected_data={
            "booking": {
                "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
                "destination": {"place_id": "p2", "display_name": "Times City"},
                "phone_number": "0901234567",
            }
        },
        confirmation="AWAITING_CONFIRMATION",
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            transcript="Không phải chỗ đó, cho bác sang Royal City",
        ),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.params == {"query": "Royal City"}


@pytest.mark.asyncio
async def test_resilient_understanding_falls_back_to_rules():
    service = ResilientUnderstandingService(
        primary=FailingUnderstanding(),
        fallback=RuleBasedUnderstanding(),
    )

    result = await service.understand(
        "Tôi muốn đặt xe",
        UnderstandingContext(session_id="session-001"),
    )

    assert result.intent is UnderstandingIntent.RIDE_BOOKING


@pytest.mark.asyncio
async def test_openai_adapter_uses_responses_structured_output():
    expected = UnderstandingResult(
        intent=UnderstandingIntent.TRIP_LOOKUP,
        booking_id="GSM-12345",
        confidence=0.92,
    )
    responses = FakeResponses(parsed=expected)
    adapter = OpenAIUnderstandingAdapter(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(responses),
    )

    result = await adapter.understand(
        "Xe tôi gọi lúc nãy tới đâu rồi?",
        UnderstandingContext(session_id="session-001"),
    )

    assert result == expected
    assert responses.calls[0]["text_format"] is UnderstandingResult
    assert responses.calls[0]["store"] is False
    assert responses.calls[0]["model"] == "test-model"


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_provider_error():
    request = SimpleNamespace(method="POST", url="https://api.openai.com")
    responses = FakeResponses(error=APIConnectionError(request=request))
    adapter = OpenAIUnderstandingAdapter(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(responses),
    )

    with pytest.raises(UnderstandingProviderError):
        await adapter.understand(
            "Tôi muốn đặt xe",
            UnderstandingContext(session_id="session-001"),
        )
