import json

import jwt

from src.backend.services.livekit_service import LiveKitTokenService
from src.voice_agent.config import LiveKitVoiceSettings


def _settings() -> LiveKitVoiceSettings:
    return LiveKitVoiceSettings(
        _env_file=None,
        voice_runtime="livekit",
        livekit_url="wss://alosm.test.livekit.cloud",
        livekit_api_key="test-api-key",
        livekit_api_secret="test-api-secret-with-enough-entropy",
        livekit_agent_name="alosm-voice",
        livekit_stt_model="deepgram/nova-3",
        livekit_llm_model="google/gemma-4-31b-it",
        livekit_tts_model="cartesia/sonic-3",
        livekit_tts_voice="test-voice",
    )


def test_token_service_uses_opaque_identity_and_server_agent_dispatch() -> None:
    details = LiveKitTokenService(_settings()).issue_for_user(
        user_id="usr_private",
        app_session_id="sess_private",
        call_instance_id="11111111-1111-4111-8111-111111111111",
    )

    claims = jwt.decode(details.participant_token, options={"verify_signature": False})

    assert details.server_url == "wss://alosm.test.livekit.cloud"
    assert claims["sub"].startswith("customer-")
    assert "usr_private" not in details.participant_token
    assert claims["video"]["room"].startswith("alosm-")
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True
    assert claims["video"]["canSubscribe"] is True
    assert claims["roomConfig"]["agents"][0]["agentName"] == "alosm-voice"
    assert json.loads(claims["metadata"]) == {
        "schema_version": "1",
        "app_session_id": "sess_private",
    }


def test_same_user_session_gets_stable_room_and_identity_for_reconnect() -> None:
    service = LiveKitTokenService(_settings())

    first = jwt.decode(
        service.issue_for_user(
            user_id="usr_1",
            app_session_id="sess_1",
            call_instance_id="11111111-1111-4111-8111-111111111111",
        ).participant_token,
        options={"verify_signature": False},
    )
    second = jwt.decode(
        service.issue_for_user(
            user_id="usr_1",
            app_session_id="sess_1",
            call_instance_id="11111111-1111-4111-8111-111111111111",
        ).participant_token,
        options={"verify_signature": False},
    )

    assert first["sub"] == second["sub"]
    assert first["video"]["room"] == second["video"]["room"]


def test_new_call_instance_gets_a_fresh_room() -> None:
    service = LiveKitTokenService(_settings())

    first = jwt.decode(
        service.issue_for_user(
            user_id="usr_1",
            app_session_id="sess_1",
            call_instance_id="11111111-1111-4111-8111-111111111111",
        ).participant_token,
        options={"verify_signature": False},
    )
    second = jwt.decode(
        service.issue_for_user(
            user_id="usr_1",
            app_session_id="sess_1",
            call_instance_id="22222222-2222-4222-8222-222222222222",
        ).participant_token,
        options={"verify_signature": False},
    )

    assert first["sub"] == second["sub"]
    assert first["video"]["room"] != second["video"]["room"]
