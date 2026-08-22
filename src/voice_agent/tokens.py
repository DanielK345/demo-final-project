"""Pure LiveKit token construction shared by the control plane and smoke tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from livekit import api

from src.voice_agent.config import LiveKitVoiceSettings


@dataclass(frozen=True, slots=True)
class LiveKitConnectionDetails:
    server_url: str
    participant_token: str


def issue_connection_details(
    settings: LiveKitVoiceSettings,
    *,
    user_id: str,
    app_session_id: str,
    call_instance_id: str,
) -> LiveKitConnectionDetails:
    """Issue least-privilege credentials from trusted, non-PII identifiers."""

    settings.require_configured()

    room_digest = hashlib.sha256(f"{user_id}:{app_session_id}:{call_instance_id}".encode()).hexdigest()[:24]
    identity_digest = hashlib.sha256(user_id.encode()).hexdigest()[:20]
    room_name = f"alosm-{room_digest}"
    participant_identity = f"customer-{identity_digest}"
    metadata = json.dumps(
        {
            "schema_version": "1",
            "app_session_id": app_session_id,
        },
        separators=(",", ":"),
    )

    token = (
        api.AccessToken(
            settings.livekit_api_key.get_secret_value(),
            settings.livekit_api_secret.get_secret_value(),
        )
        .with_identity(participant_identity)
        .with_name("Khách hàng AloSM")
        .with_metadata(metadata)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=False,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=settings.livekit_agent_name,
                        metadata=metadata,
                    )
                ]
            )
        )
        .with_ttl(timedelta(seconds=settings.livekit_token_ttl_seconds))
    )
    return LiveKitConnectionDetails(
        server_url=settings.livekit_url,
        participant_token=token.to_jwt(),
    )


def issue_operator_connection_details(
    settings: LiveKitVoiceSettings,
    *,
    operator_id: str,
    handoff_id: str,
    room_name: str,
) -> LiveKitConnectionDetails:
    """Issue a short-lived, room-scoped token for an accepted operator."""

    settings.require_configured()
    metadata = json.dumps(
        {
            "schema_version": "1",
            "role": "operator",
            "operator_id": operator_id,
            "handoff_id": handoff_id,
        },
        separators=(",", ":"),
    )
    token = (
        api.AccessToken(
            settings.livekit_api_key.get_secret_value(),
            settings.livekit_api_secret.get_secret_value(),
        )
        .with_identity(f"operator-{hashlib.sha256(operator_id.encode()).hexdigest()[:20]}")
        .with_name("Tổng đài viên AloSM")
        .with_metadata(metadata)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=False,
            )
        )
        .with_ttl(timedelta(seconds=min(settings.livekit_token_ttl_seconds, 900)))
    )
    return LiveKitConnectionDetails(server_url=settings.livekit_url, participant_token=token.to_jwt())
