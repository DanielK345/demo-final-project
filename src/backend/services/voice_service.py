from __future__ import annotations

import base64
import logging
from uuid import uuid4

from src.backend.integrations.voice_client import (
    NoSpeechDetectedError,
    VoiceProviderError,
    build_voice_client,
    resolve_voice_provider,
)
from src.backend.services.session_service import SessionService
from src.backend.services.transcript_rewriter import build_transcript_rewriter
from src.config import Settings, get_settings
from src.voice.asr.biasing import correct_place_names
from src.voice.asr.groq_provider import is_known_hallucination
from src.voice.text.gazetteer import Gazetteer
from src.voice.text.place_aliases import PlaceAliasCatalog
from src.voice.text.normalizer import normalize_transcript
from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice.tts.orchestrator import get_tts_orchestrator

logger = logging.getLogger("uvicorn.error")

ASR_REPROMPT_MESSAGE = "Tôi không nghe rõ yêu cầu của bạn, vui lòng nói rõ lại."


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
        self.place_aliases = PlaceAliasCatalog.load()
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
        try:
            raw_transcript = await voice_client.transcribe(
                audio_bytes,
                mime_type=mime_type or "audio/webm",
                prompt_hint=self.gazetteer.as_prompt_hint(),
            )
        except NoSpeechDetectedError:
            logger.info("Voice STT returned no speech session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="no_speech_detected")

        logger.info(
            "Voice transcript input session=%s provider=%s transcript=%r",
            session_id,
            provider_name,
            raw_transcript,
        )
        if not raw_transcript.strip():
            logger.info("Voice STT returned a blank transcript session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="no_speech_detected")

        deterministic_transcript = normalize_transcript(correct_place_names(raw_transcript, self.gazetteer))
        alias_corrected_transcript = self.place_aliases.correct(deterministic_transcript)
        alias_applied = alias_corrected_transcript != deterministic_transcript
        if alias_applied:
            logger.info(
                "Voice place alias corrected session=%s input=%r output=%r",
                session_id,
                deterministic_transcript,
                alias_corrected_transcript,
            )
        deterministic_transcript = alias_corrected_transcript
        if is_known_hallucination(deterministic_transcript):
            logger.info("Voice STT hallucination blocked session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="known_asr_hallucination")

        session_context = self.session_service.get_session(session_id)
        rewrite = await self._rewrite(
            deterministic_transcript,
            session_context=session_context,
            session_id=session_id,
        )
        transcript = rewrite.normalized_text
        logger.info(
            "Voice transcript after rewrite session=%s input=%r output=%r applied=%s reason=%s confidence=%s",
            session_id,
            deterministic_transcript,
            transcript,
            rewrite.applied,
            rewrite.reason,
            rewrite.confidence,
        )

        # The REST /voice/turn path may use OpenAI or Gemini rather than the
        # Groq provider. Apply the same known-hallucination guard here so this
        # caption-like ASR output never reaches the Agent.
        if is_known_hallucination(transcript):
            logger.info("Voice STT hallucination blocked session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="known_asr_hallucination")

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
        logger.info(
            "Voice TTS used session=%s provider=%s voice=%s fallback=%s duration_ms=%s",
            session_id,
            tts_result.provider,
            tts_result.voice,
            tts_result.fallback_used,
            tts_result.duration_ms,
        )

        return {
            "transcript": transcript,
            "transcript_rewritten": alias_applied or rewrite.applied,
            "transcript_rewrite_confidence": rewrite.confidence,
            "transcript_rewrite_reason": "alias_catalog_applied" if alias_applied and not rewrite.applied else rewrite.reason,
            "transcript_rewrite": self._rewrite_trace(rewrite, alias_applied=alias_applied),
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

    @staticmethod
    def _reprompt_response(provider_name: str, *, reason: str) -> dict[str, object]:
        """Return the complete REST voice response for silence or ASR hallucinations."""
        return {
            "transcript": "",
            "transcript_rewritten": False,
            "transcript_rewrite_confidence": None,
            "transcript_rewrite_reason": reason,
            "transcript_rewrite": {
                "provider": "none",
                "called": False,
                "applied": False,
                "status": reason,
            },
            "stt_confidence": 0.0,
            "message_id": f"msg_{uuid4().hex[:10]}",
            "action": "ASK_USER",
            "message": ASR_REPROMPT_MESSAGE,
            "state": {},
            "booking": None,
            "audio_base64": None,
            "audio_mime_type": "audio/mpeg",
            "voice_provider": provider_name,
            "tts_provider": None,
            "tts_voice": None,
            "tts_fallback_used": False,
            "tts_duration_ms": None,
            "tts_review_decision": None,
            "tts_review_reason_codes": [],
        }

    @staticmethod
    def _rewrite_trace(rewrite: TranscriptRewriteResult, *, alias_applied: bool = False) -> dict[str, object]:
        skipped_reasons = {"disabled_or_unconfigured", "empty", "too_long"}
        return {
            "provider": "alias_catalog+openai-compatible" if alias_applied and rewrite.model else (
                "alias_catalog" if alias_applied else "openai-compatible" if rewrite.model else "none"
            ),
            "called": rewrite.reason not in skipped_reasons,
            "applied": alias_applied or rewrite.applied,
            "status": "alias_catalog_applied" if alias_applied and not rewrite.applied else rewrite.reason,
        }
