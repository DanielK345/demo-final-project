from __future__ import annotations

import base64

from src.backend.integrations.voice_client import (
    VoiceProviderError,
    build_voice_client,
    resolve_voice_provider,
)
from src.backend.services.session_service import SessionService
from src.config import Settings, get_settings
from src.voice.asr.groq_provider import is_known_hallucination


ASR_REPROMPT_MESSAGE = "Tôi không nghe rõ yêu cầu của bạn, vui lòng nói rõ lại."


class VoiceService:
    DEFAULT_STT_CONFIDENCE = 0.92

    def __init__(
        self,
        session_service: SessionService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_service = session_service or SessionService()
        self.settings = settings or get_settings()

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
        transcript = await voice_client.transcribe(
            audio_bytes,
            mime_type=mime_type or "audio/webm",
        )

        # The REST /voice/turn path may use OpenAI or Gemini rather than the
        # Groq provider. Apply the same known-hallucination guard here so this
        # caption-like ASR output never reaches the Agent.
        if is_known_hallucination(transcript):
            return {
                "transcript": "",
                "stt_confidence": 0.0,
                "message_id": "",
                "action": "ASK_USER",
                "message": ASR_REPROMPT_MESSAGE,
                "state": {},
                "booking": None,
                "audio_base64": None,
                "audio_mime_type": "audio/mpeg",
                "voice_provider": provider_name,
                "transcript_rewrite": {
                    "provider": "gemini",
                    "called": False,
                    "applied": False,
                    "status": "skipped_hallucination",
                },
            }

        agent_result = await self.session_service.process_message(
            session_id,
            transcript,
            self.DEFAULT_STT_CONFIDENCE,
            source="VOICE",
        )
        reply_text = str(agent_result["message"])

        audio_base64 = None
        audio_mime_type = "audio/mpeg"
        if provider_name == "openai":
            try:
                audio_reply = await voice_client.synthesize(reply_text)
                audio_base64 = base64.b64encode(audio_reply).decode("ascii")
            except VoiceProviderError:
                audio_base64 = None

        return {
            "transcript": str(agent_result.get("transcript", transcript)),
            "transcript_rewrite": agent_result.get("transcript_rewrite", {}),
            "stt_confidence": self.DEFAULT_STT_CONFIDENCE,
            "message_id": agent_result["message_id"],
            "action": agent_result["action"],
            "message": reply_text,
            "state": agent_result.get("state", {}),
            "booking": agent_result.get("booking"),
            "audio_base64": audio_base64,
            "audio_mime_type": audio_mime_type,
            "voice_provider": provider_name,
        }
