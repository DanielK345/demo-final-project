"""Server-side LiveKit connection token issuance."""

from __future__ import annotations

from src.voice_agent.config import LiveKitVoiceSettings, get_livekit_voice_settings
from src.voice_agent.tokens import LiveKitConnectionDetails, issue_connection_details


class LiveKitTokenService:
    """Issue least-privilege room credentials from trusted AloSM identity data."""

    def __init__(self, settings: LiveKitVoiceSettings) -> None:
        self._settings = settings

    @property
    def agent_name(self) -> str:
        return self._settings.livekit_agent_name

    def issue_for_user(
        self,
        *,
        user_id: str,
        app_session_id: str,
        call_instance_id: str,
    ) -> LiveKitConnectionDetails:
        return issue_connection_details(
            self._settings,
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_instance_id,
        )


async def get_livekit_token_service() -> LiveKitTokenService:
    """Resolve the request-scoped token service without a threadpool hop."""
    return LiveKitTokenService(get_livekit_voice_settings())
