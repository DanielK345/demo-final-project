from __future__ import annotations

import base64

from src.backend.integrations.voice_client import (
    VoiceProviderError,
    build_voice_client,
    resolve_voice_provider,
)
from src.backend.services.session_service import SessionService
from src.backend.config import Settings, get_settings


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
            "transcript": transcript,
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
