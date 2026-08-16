from __future__ import annotations

import base64

from src.backend.integrations.voice_client import (
    VoiceProviderError,
    build_voice_client,
    resolve_voice_provider,
)
from src.backend.services.session_service import SessionService
from src.backend.services.transcript_rewriter import build_transcript_rewriter
from src.config import Settings, get_settings
from src.voice.asr.biasing import correct_place_names
from src.voice.text.gazetteer import Gazetteer
from src.voice.text.normalizer import normalize_transcript
from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice.tts.orchestrator import get_tts_orchestrator


class VoiceService:
    def __init__(
        self,
        session_service: SessionService | None = None,
        settings: Settings | None = None,
        transcript_rewriter: TranscriptRewriter | None = None,
    ) -> None:
        self.session_service = session_service or SessionService()
        self.settings = settings or get_settings()
        self.gazetteer = Gazetteer.load()
        self.transcript_rewriter = transcript_rewriter or build_transcript_rewriter(self.settings, self.gazetteer)

    async def process_turn(
        self,
        session_id: str,
        audio_bytes: bytes,
        *,
        mime_type: str | None = None,
    ) -> dict[str, object]:
        if not audio_bytes:
            raise VoiceProviderError("Audio recording is empty")

        provider_name = resolve_voice_provider(self.settings)
        voice_client = build_voice_client(self.settings)
        raw_transcript = await voice_client.transcribe(
            audio_bytes,
            mime_type=mime_type or "audio/webm",
            prompt_hint=self.gazetteer.as_prompt_hint(),
        )
        deterministic_transcript = normalize_transcript(correct_place_names(raw_transcript, self.gazetteer))
        session_context = self.session_service.get_session(session_id)
        rewrite = await self._rewrite(
            deterministic_transcript,
            session_context=session_context,
            session_id=session_id,
        )
        transcript = rewrite.normalized_text

        agent_result = await self.session_service.process_message(
            session_id,
            transcript,
            None,
            source="VOICE",
        )
        reply_text = str(agent_result["message"])

        booking_confirmed = (agent_result.get("state") or {}).get("booking_lifecycle_status") == "SUCCESS"
        tts_result = await get_tts_orchestrator().synthesize(
            reply_text,
            review_context={"booking_confirmed": booking_confirmed, "action": agent_result.get("action")},
        )
        audio_base64 = base64.b64encode(tts_result.audio).decode("ascii")

        return {
            "transcript": transcript,
            "transcript_rewritten": rewrite.applied,
            "transcript_rewrite_confidence": rewrite.confidence,
            "transcript_rewrite_reason": rewrite.reason,
            "stt_confidence": None,
            "message_id": agent_result["message_id"],
            "action": agent_result["action"],
            "message": reply_text,
            "state": agent_result.get("state", {}),
            "booking": agent_result.get("booking"),
            "audio_base64": audio_base64,
            "audio_mime_type": tts_result.mime_type,
            "voice_provider": provider_name,
            "tts_provider": tts_result.provider,
            "tts_voice": tts_result.voice,
            "tts_fallback_used": tts_result.fallback_used,
            "tts_duration_ms": tts_result.duration_ms,
            "tts_review_decision": tts_result.review_decision,
            "tts_review_reason_codes": tts_result.review_reason_codes,
        }

    async def _rewrite(
        self,
        text: str,
        *,
        session_context: dict[str, object],
        session_id: str,
    ) -> TranscriptRewriteResult:
        if self.transcript_rewriter is None:
            return TranscriptRewriteResult(
                raw_text=text,
                normalized_text=text,
                reason="disabled_or_unconfigured",
            )
        return await self.transcript_rewriter.rewrite(
            text,
            session_context=session_context,
            session_id=session_id,
        )
