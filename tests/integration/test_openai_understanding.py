import os

import pytest

from src.agents.agent import LLMAgent
from src.agents.schemas import ActionType, AgentInput, ToolName
from src.agents.understanding.models import (
    ConfirmationIntent,
    CorrectionField,
    UnderstandingContext,
    UnderstandingIntent,
)
from src.agents.understanding.openai import OpenAIUnderstandingAdapter
from src.config import get_settings

pytestmark = [
    pytest.mark.provider,
    pytest.mark.skipif(
        os.getenv("RUN_OPENAI_INTEGRATION") != "1",
        reason="set RUN_OPENAI_INTEGRATION=1 to call the real OpenAI API",
    ),
]


def build_adapter() -> OpenAIUnderstandingAdapter:
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        pytest.skip("OPENAI_API_KEY is required")
    return OpenAIUnderstandingAdapter(
        api_key=api_key,
        model=settings.agent_llm_model,
        timeout_seconds=max(settings.agent_llm_timeout_seconds, 15),
        reasoning_effort=settings.agent_llm_reasoning_effort,
        base_url=settings.agent_llm_base_url,
    )


@pytest.mark.asyncio
async def test_openai_understands_natural_vietnamese_booking_request():
    result = await build_adapter().understand(
        "Bác đang đứng gần cổng Vinmec, gọi xe cho bác về Times City nhé",
        UnderstandingContext(session_id="provider-booking"),
    )

    assert result.intent is UnderstandingIntent.RIDE_BOOKING
    assert result.pickup_query
    assert "Vinmec" in result.pickup_query
    assert result.destination_query
    assert "Times City" in result.destination_query


@pytest.mark.asyncio
async def test_openai_understands_lookup_correction_and_confirmation():
    adapter = build_adapter()
    lookup = await adapter.understand(
        "Chiếc xe tôi gọi lúc nãy tới đâu rồi?",
        UnderstandingContext(session_id="provider-lookup"),
    )
    correction = await adapter.understand(
        "Không đón ở Hồ Gươm nữa, đổi điểm đón sang Nhà hát Lớn",
        UnderstandingContext(
            session_id="provider-correction",
            current_workflow="RIDE_BOOKING",
            current_step="CONFIRM",
            known_fields=["booking.pickup", "booking.destination"],
        ),
    )
    confirmation = await adapter.understand(
        "Vâng đúng rồi, đặt giúp bác",
        UnderstandingContext(
            session_id="provider-confirmation",
            current_workflow="RIDE_BOOKING",
            current_step="CONFIRM",
        ),
    )

    assert lookup.intent is UnderstandingIntent.TRIP_LOOKUP
    assert any(item.field is CorrectionField.PICKUP and "Nhà hát Lớn" in item.value for item in correction.corrections)
    assert confirmation.confirmation is ConfirmationIntent.CONFIRM


@pytest.mark.asyncio
async def test_openai_understanding_drives_core_agent_booking_action():
    agent = LLMAgent(understanding_service=build_adapter())

    action = await agent.handle(
        AgentInput(
            session_id="provider-core-booking",
            turn_id="turn-001",
            transcript="Bác đang ở cổng Vinmec, gọi xe đưa bác về Times City nhé",
        )
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert "Vinmec" in action.tool_call.params["query"]
