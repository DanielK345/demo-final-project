import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": ""})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_returns_session_id(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["user_id"] == "usr_demo"
    assert data["session_id"].startswith("sess_")


@pytest.mark.asyncio
async def test_create_session_requires_auth(client):
    response = await client.post(
        "/api/v1/sessions",
        json={"channel": "WEB_VOICE", "device_id": "browser"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_returns_cached_session(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]
    session_id = login.json()["session_id"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
