from __future__ import annotations

import base64
import logging
from uuid import uuid4

from src.backend.integrations.voice_client import (
    NoSpeechDetectedError,
    OpenAIVoiceClient,
    VoiceProviderError,
    build_voice_client,
    resolve_voice_provider,
    synthesize_with_openai_tts,
)
from src.backend.services.session_service import SessionService
from src.backend.services.transcript_rewriter import build_transcript_rewriter
from src.config import Settings, get_settings
from src.voice.asr.biasing import correct_place_names
from src.voice.asr.brief_sound import detect_brief_ambiguous_sound
from src.voice.asr.groq_provider import is_known_hallucination
from src.voice.text.gazetteer import Gazetteer
from src.voice.text.normalizer import normalize_transcript
from src.voice.text.place_aliases import PlaceAliasCatalog
from src.voice.text.rewrite_contract import TranscriptRewriter, TranscriptRewriteResult
from src.voice.tts.errors import TTSError
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

        try:
            provider_name = resolve_voice_provider(self.settings)
            voice_client = build_voice_client(self.settings)
        except VoiceProviderError:
            if not self.settings.openai_api_key:
                raise
            provider_name = f"openai:{self.settings.voice_stt_fallback_model}"
            voice_client = OpenAIVoiceClient(
                self.settings,
                transcription_model=self.settings.voice_stt_fallback_model,
            )
            logger.warning("Primary STT unavailable; using fallback provider=%s", provider_name)
        try:
            raw_transcript = await voice_client.transcribe(
                audio_bytes,
                mime_type=mime_type or "audio/webm",
                prompt_hint=self.gazetteer.as_prompt_hint(),
            )
        except NoSpeechDetectedError:
            logger.info("Voice STT returned no speech session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="no_speech_detected")
        except VoiceProviderError as primary_error:
            if provider_name.startswith("openai") or not self.settings.openai_api_key:
                raise
            fallback_model = self.settings.voice_stt_fallback_model
            logger.warning(
                "Voice STT failed session=%s provider=%s error_type=%s; falling back to OpenAI model=%s",
                session_id,
                provider_name,
                type(primary_error).__name__,
                fallback_model,
            )
            fallback_client = OpenAIVoiceClient(self.settings, transcription_model=fallback_model)
            try:
                raw_transcript = await fallback_client.transcribe(
                    audio_bytes,
                    mime_type=mime_type or "audio/webm",
                    prompt_hint=self.gazetteer.as_prompt_hint(),
                )
            except NoSpeechDetectedError:
                logger.info(
                    "Voice fallback STT returned no speech session=%s provider=openai model=%s",
                    session_id,
                    fallback_model,
                )
                return self._reprompt_response(
                    f"openai:{fallback_model}",
                    reason="no_speech_detected",
                )
            provider_name = f"openai:{fallback_model}"

        logger.info(
            "Voice transcript input session=%s provider=%s transcript=%r",
            session_id,
            provider_name,
            raw_transcript,
        )
        if not raw_transcript.strip():
            logger.info("Voice STT returned a blank transcript session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="no_speech_detected")

        normalized_raw_transcript = normalize_transcript(raw_transcript)
        if self.settings.voice_brief_ambiguous_sound_enabled:
            brief_sound = detect_brief_ambiguous_sound(
                normalized_raw_transcript,
                max_duration_ms=self.settings.voice_brief_ambiguous_sound_max_duration_ms,
                low_confidence_threshold=self.settings.voice_brief_ambiguous_sound_max_confidence,
            )
            if brief_sound.blocked:
                logger.info(
                    "Voice brief ambiguous sound blocked session=%s provider=%s transcript=%r",
                    session_id,
                    provider_name,
                    normalized_raw_transcript,
                )
                return self._reprompt_response(
                    provider_name,
                    reason=brief_sound.reason or "brief_ambiguous_sound",
                )
        # Correct known multi-token ASR aliases before fuzzy gazetteer matching.
        # Otherwise "Bình Yuni" can become "Bình VinUni" when the one-token
        # fuzzy matcher replaces only "Yuni", preventing the exact phrase alias
        # from matching afterward.
        alias_corrected_transcript = self.place_aliases.correct(normalized_raw_transcript)
        alias_applied = alias_corrected_transcript != normalized_raw_transcript
        if alias_applied:
            logger.info(
                "Voice place alias corrected session=%s input=%r output=%r",
                session_id,
                normalized_raw_transcript,
                alias_corrected_transcript,
            )
        deterministic_transcript = normalize_transcript(
            correct_place_names(alias_corrected_transcript, self.gazetteer)
        )
        if is_known_hallucination(deterministic_transcript):
            logger.info("Voice STT hallucination blocked session=%s provider=%s", session_id, provider_name)
            return self._reprompt_response(provider_name, reason="known_asr_hallucination")

        durable_getter = getattr(self.session_service, "get_session_durable", None)
        session_context = (
            await durable_getter(session_id)
            if durable_getter is not None
            else self.session_service.get_session(session_id)
        )
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
        tts_result = await self._synthesize_reply(
            session_id,
            reply_text,
            review_context={"booking_confirmed": booking_confirmed, "action": agent_result.get("action")},
        )

        audio_base64 = base64.b64encode(tts_result.audio).decode("ascii") if tts_result else None
        if tts_result:
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
            "audio_mime_type": tts_result.mime_type if tts_result else "audio/mpeg",
            "voice_provider": provider_name,
            "tts_provider": tts_result.provider if tts_result else "unavailable",
            "tts_voice": tts_result.voice if tts_result else None,
            "tts_fallback_used": tts_result.fallback_used if tts_result else True,
            "tts_duration_ms": tts_result.duration_ms if tts_result else None,
            "tts_review_decision": tts_result.review_decision if tts_result else None,
            "tts_review_reason_codes": tts_result.review_reason_codes if tts_result else [],
        }

    async def _synthesize_reply(
        self,
        session_id: str,
        reply_text: str,
        *,
        review_context: dict[str, object],
    ):
        """Use configured primary TTS and keep the successful agent turn on failure."""
        orchestrator = get_tts_orchestrator()
        if self.settings.voice_tts_provider == "openai" and self.settings.openai_api_key:
            try:
                return await synthesize_with_openai_tts(
                    reply_text,
                    self.settings,
                    fallback_used=False,
                    review_context=review_context,
                )
            except VoiceProviderError as openai_error:
                logger.warning(
                    "OpenAI TTS primary failed session=%s error_type=%s; trying Edge fallback",
                    session_id,
                    type(openai_error).__name__,
                )
                try:
                    result = await orchestrator.synthesize(
                        reply_text,
                        review_context=review_context,
                    )
                    result.fallback_used = True
                    return result
                except TTSError as edge_error:
                    return self._text_only_after_tts_failure(session_id, edge_error)

        if self.settings.voice_tts_provider == "openai":
            logger.warning(
                "OPENAI_API_KEY is missing; using Edge TTS fallback session=%s",
                session_id,
            )
        try:
            return await orchestrator.synthesize(
                reply_text,
                review_context=review_context,
            )
        except TTSError as edge_error:
            if edge_error.status_code != 503 or not self.settings.openai_api_key:
                if edge_error.status_code != 503:
                    raise
                return self._text_only_after_tts_failure(session_id, edge_error)
            logger.warning(
                "Edge TTS unavailable session=%s code=%s; trying OpenAI TTS fallback",
                session_id,
                edge_error.code,
            )
            try:
                return await synthesize_with_openai_tts(
                    reply_text,
                    self.settings,
                    fallback_used=True,
                    review_context=review_context,
                )
            except VoiceProviderError as openai_error:
                return self._text_only_after_tts_failure(session_id, openai_error)

    @staticmethod
    def _text_only_after_tts_failure(session_id: str, error: Exception):
        # The agent turn already succeeded. Do not lose conversation state merely
        # because every server TTS backend is unavailable; the UI can speak locally.
        logger.warning(
            "All server TTS providers unavailable session=%s error_type=%s; returning text-only",
            session_id,
            type(error).__name__,
        )
        return None

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
