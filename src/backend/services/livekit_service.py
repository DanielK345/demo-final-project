"""Server-side LiveKit connection token issuance."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from livekit import api

from src.voice_agent.config import LiveKitVoiceSettings, get_livekit_voice_settings
from src.voice_agent.tokens import LiveKitConnectionDetails, issue_connection_details, issue_operator_connection_details


@dataclass(frozen=True, slots=True)
class PreparedLiveKitConnection:
    details: LiveKitConnectionDetails
    agent_prepared: bool


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

    def issue_for_operator(self, *, operator_id: str, handoff_id: str, room_name: str) -> LiveKitConnectionDetails:
        return issue_operator_connection_details(
            self._settings,
            operator_id=operator_id,
            handoff_id=handoff_id,
            room_name=room_name,
        )

    async def prepare_for_user(
        self,
        *,
        user_id: str,
        app_session_id: str,
        call_instance_id: str,
    ) -> PreparedLiveKitConnection:
        """Dispatch the agent before browser Room connection, with token fallback."""
        details = self.issue_for_user(
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_instance_id,
        )
        from src.voice_agent.tokens import build_call_target

        target = build_call_target(
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_instance_id,
        )
        prepared = False
        try:
            async with api.LiveKitAPI(
                url=self._settings.livekit_url,
                api_key=self._settings.livekit_api_key.get_secret_value(),
                api_secret=self._settings.livekit_api_secret.get_secret_value(),
            ) as livekit_api:
                await livekit_api.agent_dispatch.create_dispatch(
                    api.CreateAgentDispatchRequest(
                        agent_name=self._settings.livekit_agent_name,
                        room=target.room_name,
                        metadata=target.metadata,
                    )
                )
            prepared = True
        except Exception as exc:
            logger.warning(
                "LiveKit early agent dispatch failed open room=%s error_type=%s",
                target.room_name,
                type(exc).__name__,
            )
        return PreparedLiveKitConnection(details=details, agent_prepared=prepared)


async def get_livekit_token_service() -> LiveKitTokenService:
    """Resolve the request-scoped token service without a threadpool hop."""
    return LiveKitTokenService(get_livekit_voice_settings())
