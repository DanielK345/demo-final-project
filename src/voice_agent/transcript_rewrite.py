"""Post-STT transcript rewriting at LiveKit's pre-LLM lifecycle hook."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from livekit.agents import llm

from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice_agent.session_data import AloSMSessionData, BookingDraft

logger = logging.getLogger(__name__)

MINIMUM_ASR_CONFIDENCE = 0.45
DEFAULT_REWRITE_TIMEOUT_SECONDS = 5.0
REWRITE_TIMEOUT_GRACE_SECONDS = 0.25


def _booking_step(draft: BookingDraft) -> str:
    if draft.confirmation_status == "awaiting":
        return "CONFIRM"
    if draft.pickup is None:
        return "SELECT_PICKUP_CANDIDATE" if len(draft.pickup_candidates) >= 2 else "COLLECT_PICKUP"
    if draft.destination is None:
        return "SELECT_DESTINATION_CANDIDATE" if len(draft.destination_candidates) >= 2 else "COLLECT_DESTINATION"
    if draft.vehicle_type is None:
        return "COLLECT_VEHICLE"
    if draft.quote is None:
        return "ESTIMATE_FARE"
    if draft.confirmation_status == "confirmed":
        return "CREATE_BOOKING"
    return "PRESENT_QUOTE"


def _rewrite_context(
    userdata: AloSMSessionData,
    turn_ctx: llm.ChatContext,
) -> dict[str, Any]:
    """Project typed LiveKit state into the rewriter's privacy-minimal contract."""

    step = _booking_step(userdata.booking_draft)
    history: list[dict[str, str]] = []
    for item in reversed(turn_ctx.items):
        if isinstance(item, llm.ChatMessage) and item.role == "assistant" and item.text_content:
            history.append({"role": "ASSISTANT", "content": item.text_content})
            break
    return {
        "current_workflow": "BOOKING",
        "current_step": step,
        "agent_state": {
            "current_workflow": "BOOKING",
            "current_step": step,
            "collected_data": {
                "booking": userdata.booking_draft.model_dump(mode="json"),
            },
            "conversation_history": history,
        },
    }


async def rewrite_livekit_user_turn(
    *,
    rewriter: TranscriptRewriter | None,
    userdata: AloSMSessionData | None,
    turn_ctx: llm.ChatContext,
    new_message: llm.ChatMessage,
) -> TranscriptRewriteResult | None:
    """Rewrite one finalized user turn before LiveKit adds it to LLM context.

    Provider failures fail open to the original transcript. A low-confidence audio
    turn is left untouched so the booking task's existing clarification guard can
    handle it without an LLM making the words appear more certain.
    """

    text = (new_message.text_content or "").strip()
    confidence = new_message.transcript_confidence
    if not text:
        return None
    if rewriter is None or userdata is None:
        logger.info(
            "LiveKit transcript rewrite bypassed item_id=%s reason=disabled_or_unconfigured",
            new_message.id,
        )
        return TranscriptRewriteResult(
            raw_text=text,
            normalized_text=text,
            reason="disabled_or_unconfigured",
            duration_ms=0,
        )
    if confidence is not None and confidence < MINIMUM_ASR_CONFIDENCE:
        logger.info(
            "LiveKit transcript rewrite skipped reason=low_asr_confidence confidence=%.2f",
            confidence,
        )
        return TranscriptRewriteResult(
            raw_text=text,
            normalized_text=text,
            reason="low_asr_confidence",
            duration_ms=0,
        )

    configured_timeout = getattr(rewriter, "timeout_seconds", DEFAULT_REWRITE_TIMEOUT_SECONDS)
    try:
        timeout_seconds = max(float(configured_timeout), 0.1)
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_REWRITE_TIMEOUT_SECONDS
    hard_timeout_seconds = timeout_seconds + REWRITE_TIMEOUT_GRACE_SECONDS
    started = time.monotonic()
    logger.info(
        "LiveKit transcript rewrite started item_id=%s input_length=%d confidence=%s "
        "timeout_seconds=%.2f",
        new_message.id,
        len(text),
        confidence,
        timeout_seconds,
    )
    try:
        async with asyncio.timeout(hard_timeout_seconds):
            result = await rewriter.rewrite(
                text,
                session_context=_rewrite_context(userdata, turn_ctx),
                session_id=userdata.app_session_id,
            )
    except TimeoutError:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "LiveKit transcript rewrite timed out item_id=%s duration_ms=%d "
            "hard_timeout_seconds=%.2f; using raw transcript",
            new_message.id,
            duration_ms,
            hard_timeout_seconds,
        )
        return TranscriptRewriteResult(
            raw_text=text,
            normalized_text=text,
            reason="provider_timeout",
            duration_ms=duration_ms,
        )
    except Exception as exc:
        logger.warning(
            "LiveKit transcript rewrite failed open error_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        return TranscriptRewriteResult(
            raw_text=text,
            normalized_text=text,
            reason="provider_error",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if result.applied and result.normalized_text.strip():
        non_text_content = [item for item in new_message.content if not isinstance(item, str)]
        new_message.content = [result.normalized_text, *non_text_content]

    elapsed_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "LiveKit transcript rewrite completed item_id=%s applied=%s reason=%s confidence=%s "
        "provider_duration_ms=%s elapsed_ms=%d input_length=%d output_length=%d",
        new_message.id,
        result.applied,
        result.reason,
        result.confidence,
        result.duration_ms,
        elapsed_ms,
        len(text),
        len(result.normalized_text),
    )
    return result
