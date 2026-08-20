import pytest

from src.backend.services.livekit_service import (
    LiveKitConnectionDetails,
    get_livekit_token_service,
)
from src.main import app


class FakeLiveKitTokenService:
    agent_name = "alosm-voice"

    def issue_for_user(
        self,
        *,
        user_id: str,
        app_session_id: str,
        call_instance_id: str,
    ) -> LiveKitConnectionDetails:
        assert user_id
        assert app_session_id
        assert call_instance_id
        return LiveKitConnectionDetails(
            server_url="wss://alosm.test.livekit.cloud",
            participant_token="signed-test-token",
        )


async def get_fake_livekit_token_service() -> FakeLiveKitTokenService:
    return FakeLiveKitTokenService()


@pytest.fixture
def livekit_service_override():
    app.dependency_overrides[get_livekit_token_service] = get_fake_livekit_token_service
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_livekit_token_service, None)


@pytest.mark.asyncio
async def test_livekit_token_requires_authentication(client, livekit_service_override) -> None:
    response = await client.post("/api/v1/livekit/token", json={"agent_name": "alosm-voice"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_livekit_token_returns_standard_endpoint_contract(client, livekit_service_override) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/livekit/token",
        json={
            "agent_name": "alosm-voice",
            "participant_attributes": {"alosm.call_id": "11111111-1111-4111-8111-111111111111"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "server_url": "wss://alosm.test.livekit.cloud",
        "participant_token": "signed-test-token",
    }


@pytest.mark.asyncio
async def test_livekit_token_rejects_client_controlled_identity(client, livekit_service_override) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/livekit/token",
        json={
            "agent_name": "alosm-voice",
            "participant_identity": "admin",
            "participant_attributes": {"alosm.call_id": "11111111-1111-4111-8111-111111111111"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_livekit_token_rejects_unconfigured_agent(client, livekit_service_override) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/livekit/token",
        json={
            "agent_name": "attacker-agent",
            "participant_attributes": {"alosm.call_id": "11111111-1111-4111-8111-111111111111"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_livekit_token_requires_valid_call_instance(client, livekit_service_override) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]

    missing = await client.post(
        "/api/v1/livekit/token",
        json={"agent_name": "alosm-voice"},
        headers={"Authorization": f"Bearer {token}"},
    )
    malformed = await client.post(
        "/api/v1/livekit/token",
        json={"participant_attributes": {"alosm.call_id": "not-a-uuid"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert missing.status_code == 400
    assert malformed.status_code == 400


@pytest.mark.asyncio
async def test_livekit_token_rejects_ended_application_session(client, livekit_service_override) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]
    session_id = login.json()["session_id"]
    await client.post(
        f"/api/v1/sessions/{session_id}/end",
        json={"reason": "USER_ENDED"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        "/api/v1/livekit/token",
        json={
            "agent_name": "alosm-voice",
            "participant_attributes": {"alosm.call_id": "11111111-1111-4111-8111-111111111111"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "đã kết thúc" in response.json()["detail"]
