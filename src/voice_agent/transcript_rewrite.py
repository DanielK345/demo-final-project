"""Post-STT transcript rewriting at LiveKit's pre-LLM lifecycle hook."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from livekit.agents import llm

from src.backend.services.transcript_rewriter import apply_deterministic_transcript_rewrite
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
    *,
    asr_confidence: float | None,
    context_window_turns: int,
    memory_max_corrections: int,
) -> dict[str, Any]:
    """Project typed LiveKit state into the rewriter's privacy-minimal contract."""

    step = _booking_step(userdata.booking_draft)
    history: list[dict[str, str]] = []
    if context_window_turns > 0:
        messages = [
            item
            for item in turn_ctx.items
            if isinstance(item, llm.ChatMessage)
            and item.role in {"user", "assistant"}
            and item.text_content
        ]
        for item in messages[-(context_window_turns * 2) :]:
            history.append({"role": item.role.upper(), "content": item.text_content or ""})
    return {
        "current_workflow": "BOOKING",
        "current_step": step,
        "asr_confidence": asr_confidence,
        "agent_state": {
            "current_workflow": "BOOKING",
            "current_step": step,
            "collected_data": {
                "booking": userdata.booking_draft.model_dump(mode="json"),
            },
            "conversation_history": history,
            "rewrite_memory": [
                item.model_dump(mode="json")
                for item in userdata.rewrite_memory[-memory_max_corrections:]
            ]
            if memory_max_corrections > 0
            else [],
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
    turn may receive only a uniquely grounded deterministic correction; otherwise
    it remains untouched for the booking task's clarification guard.
    """

    text = (new_message.text_content or "").strip()
    confidence = new_message.transcript_confidence
    if not text:
        return None
    context_window_turns = max(int(getattr(rewriter, "context_window_turns", 3)), 0)
    memory_max_corrections = max(int(getattr(rewriter, "memory_max_corrections", 6)), 0)
    session_context = (
        _rewrite_context(
            userdata,
            turn_ctx,
            asr_confidence=confidence,
            context_window_turns=context_window_turns,
            memory_max_corrections=memory_max_corrections,
        )
        if userdata is not None
        else {"asr_confidence": confidence}
    )
    if confidence is not None and confidence < MINIMUM_ASR_CONFIDENCE:
        normalized_text, deterministic_reason = apply_deterministic_transcript_rewrite(
            text,
            session_context,
        )
        if deterministic_reason is not None:
            non_text_content = [item for item in new_message.content if not isinstance(item, str)]
            new_message.content = [normalized_text, *non_text_content]
            if userdata is not None:
                userdata.remember_rewrite(text, normalized_text, limit=memory_max_corrections)
            logger.info(
                "LiveKit low-confidence deterministic rewrite applied item_id=%s reason=%s confidence=%.2f",
                new_message.id,
                deterministic_reason,
                confidence,
            )
            return TranscriptRewriteResult(
                raw_text=text,
                normalized_text=normalized_text,
                applied=True,
                confidence=1.0,
                reason=deterministic_reason,
                duration_ms=0,
            )
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
    if rewriter is None:
        normalized_text, deterministic_reason = apply_deterministic_transcript_rewrite(
            text,
            session_context,
        )
        if deterministic_reason is not None:
            non_text_content = [item for item in new_message.content if not isinstance(item, str)]
            new_message.content = [normalized_text, *non_text_content]
            if userdata is not None:
                userdata.remember_rewrite(text, normalized_text, limit=memory_max_corrections)
            logger.info(
                "LiveKit deterministic transcript rewrite applied item_id=%s reason=%s",
                new_message.id,
                deterministic_reason,
            )
            return TranscriptRewriteResult(
                raw_text=text,
                normalized_text=normalized_text,
                applied=True,
                confidence=1.0,
                reason=deterministic_reason,
                duration_ms=0,
            )
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
                session_context=session_context,
                session_id=userdata.app_session_id if userdata is not None else None,
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
        if userdata is not None:
            userdata.remember_rewrite(text, result.normalized_text, limit=memory_max_corrections)

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
