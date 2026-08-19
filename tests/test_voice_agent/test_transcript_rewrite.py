from typing import Any

import pytest
from livekit.agents import llm

from src.voice.text.rewrite_contract import TranscriptRewriteResult
from src.voice_agent.agent import AloSMAgent
from src.voice_agent.session_data import AloSMSessionData, PlaceCandidate
from src.voice_agent.tasks.booking import BookingTask
from src.voice_agent.transcript_rewrite import rewrite_livekit_user_turn


def _userdata() -> AloSMSessionData:
    return AloSMSessionData(
        app_session_id="session",
        call_id="call",
        user_id="user",
        participant_identity="participant",
    )


class _Rewriter:
    def __init__(self, normalized_text: str = "Alo, tôi muốn đặt xe.") -> None:
        self.normalized_text = normalized_text
        self.calls: list[dict[str, Any]] = []

    async def rewrite(
        self,
        text: str,
        *,
        session_context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> TranscriptRewriteResult:
        self.calls.append(
            {
                "text": text,
                "session_context": session_context,
                "session_id": session_id,
            }
        )
        return TranscriptRewriteResult(
            raw_text=text,
            normalized_text=self.normalized_text,
            applied=self.normalized_text != text,
            confidence=0.99,
            reason="applied",
            model="test/rewriter",
            duration_ms=12,
        )


class _FailingRewriter:
    async def rewrite(self, *_: object, **__: object) -> TranscriptRewriteResult:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_parent_agent_rewrites_final_turn_before_llm_context() -> None:
    rewriter = _Rewriter()
    userdata = _userdata()
    agent = AloSMAgent(session_data=userdata, transcript_rewriter=rewriter)
    message = llm.ChatMessage(
        role="user",
        content=["ALO TOI MUON DAT XE"],
        transcript_confidence=0.91,
    )

    await agent.on_user_turn_completed(llm.ChatContext.empty(), message)

    assert message.text_content == "Alo, tôi muốn đặt xe."
    assert message.transcript_confidence == 0.91
    assert rewriter.calls[0]["session_id"] == "session"


@pytest.mark.asyncio
async def test_booking_task_uses_same_rewrite_hook_and_booking_context() -> None:
    rewriter = _Rewriter("Tôi chọn cổng trường VinUni.")
    userdata = _userdata()
    userdata.booking_draft.set_candidates(
        "pickup",
        "VinUni",
        [
            PlaceCandidate(
                place_id="gate-a",
                display_name="Cổng A VinUni",
                address="VinUni",
                provider="test",
                asr_aliases=("cổng a bin uni",),
            ),
            PlaceCandidate(
                place_id="gate-b",
                display_name="Cổng B VinUni",
                address="VinUni",
                provider="test",
                asr_aliases=("cổng bê bin uni",),
            ),
        ],
    )
    turn_ctx = llm.ChatContext.empty()
    turn_ctx.add_message(role="assistant", content="Bạn muốn chọn cổng nào?")
    message = llm.ChatMessage(role="user", content=["toi chon cong a bin uni"])
    task = BookingTask(session_data=userdata, transcript_rewriter=rewriter)

    await task.on_user_turn_completed(turn_ctx, message)

    assert message.text_content == "Tôi chọn cổng trường VinUni."
    context = rewriter.calls[0]["session_context"]
    assert context["current_step"] == "SELECT_PICKUP_CANDIDATE"
    assert context["agent_state"]["conversation_history"][-1]["content"] == "Bạn muốn chọn cổng nào?"
    candidates = context["agent_state"]["collected_data"]["booking"]["pickup_candidates"]
    assert candidates[0]["asr_aliases"] == ["cổng a bin uni"]


@pytest.mark.asyncio
async def test_low_confidence_audio_skips_rewrite_for_existing_clarification_guard() -> None:
    rewriter = _Rewriter()
    message = llm.ChatMessage(role="user", content=["ờ"], transcript_confidence=0.2)

    result = await rewrite_livekit_user_turn(
        rewriter=rewriter,
        userdata=_userdata(),
        turn_ctx=llm.ChatContext.empty(),
        new_message=message,
    )

    assert result is None
    assert message.text_content == "ờ"
    assert rewriter.calls == []


@pytest.mark.asyncio
async def test_rewrite_provider_failure_fails_open_to_raw_transcript() -> None:
    message = llm.ChatMessage(role="user", content=["alo toi muon dat xe"])

    result = await rewrite_livekit_user_turn(
        rewriter=_FailingRewriter(),
        userdata=_userdata(),
        turn_ctx=llm.ChatContext.empty(),
        new_message=message,
    )

    assert result is None
    assert message.text_content == "alo toi muon dat xe"
