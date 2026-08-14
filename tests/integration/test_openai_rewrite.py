import os

import pytest

from src.agents.context_models import (
    CandidateField,
    ContextCandidate,
    ContextMessage,
    ConversationContext,
)
from src.agents.state import ConversationRole, DeliveryStatus
from src.agents.understanding.rewrite_models import RewriteDecision, RewriteReason
from src.agents.understanding.rewrite_openai import OpenAIContextualRewriteAdapter
from src.agents.understanding.rewrite_service import ResilientContextualRewriteService
from src.config import get_settings

pytestmark = [
    pytest.mark.provider,
    pytest.mark.skipif(
        os.getenv("RUN_OPENAI_INTEGRATION") != "1",
        reason="set RUN_OPENAI_INTEGRATION=1 to call the real OpenAI API",
    ),
]


def build_service() -> ResilientContextualRewriteService:
    settings = get_settings()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY is required")
    return ResilientContextualRewriteService(
        OpenAIContextualRewriteAdapter(
            api_key=settings.openai_api_key,
            model=settings.agent_rewrite_model,
            timeout_seconds=max(settings.agent_rewrite_timeout_seconds, 15),
            reasoning_effort=settings.agent_rewrite_reasoning_effort,
            base_url=settings.agent_rewrite_base_url,
        )
    )


@pytest.mark.asyncio
async def test_openai_rewrite_resolves_ordinal_from_delivered_candidates():
    original = "Ừ, cái thứ hai ấy"
    context = ConversationContext(
        session_id="provider-rewrite-selection",
        raw_transcript=original,
        current_workflow="RIDE_BOOKING",
        current_step="SELECT_PICKUP_CANDIDATE",
        available_candidates=[
            ContextCandidate(
                field=CandidateField.PICKUP,
                index=1,
                display_name="Hồ Hoàn Kiếm",
            ),
            ContextCandidate(
                field=CandidateField.PICKUP,
                index=2,
                display_name="Phố đi bộ Hồ Gươm",
            ),
        ],
        recent_messages=[
            ContextMessage(
                message_id="turn-001:assistant",
                turn_id="turn-001",
                role=ConversationRole.ASSISTANT,
                content=(
                    "Tôi tìm thấy 1. Hồ Hoàn Kiếm và 2. Phố đi bộ Hồ Gươm. "
                    "Bạn chọn số mấy?"
                ),
                delivery_status=DeliveryStatus.DELIVERED,
            )
        ],
        character_budget=4000,
    )

    result = await build_service().rewrite(
        original,
        context,
        RewriteDecision(
            should_rewrite=True,
            reasons=[RewriteReason.ORDINAL_SELECTION],
        ),
    )

    assert result.changed is True
    assert "Phố đi bộ Hồ Gươm" in result.rewritten_text
    assert result.resolved_references


@pytest.mark.asyncio
async def test_openai_rewrite_does_not_invent_home_address_without_context():
    original = "Cho tôi về nhà"
    context = ConversationContext(
        session_id="provider-rewrite-home",
        raw_transcript=original,
        current_workflow="RIDE_BOOKING",
        current_step="COLLECT_DESTINATION",
        character_budget=4000,
    )

    result = await build_service().rewrite(
        original,
        context,
        RewriteDecision(
            should_rewrite=True,
            reasons=[RewriteReason.SHORT_CONTEXTUAL_REPLY],
        ),
    )

    assert result.changed is False
    assert result.rewritten_text == original
