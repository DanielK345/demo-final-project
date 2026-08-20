import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_checks_database_without_leaking_configuration(client):
    response = await client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["configuration"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["asr"] == "failed"
    assert payload["error_codes"] == ["ASR_NOT_READY"]
    assert "DATABASE_URL" not in response.text

@pytest.mark.asyncio
async def test_chat_empty_message(client):
    response = await client.post(
        "/api/v1/chat",
        json={"turn_id": "turn-001", "message": ""},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_chat_requires_turn_id(client):
    response = await client.post(
        "/api/v1/chat",
        json={"message": "Tôi muốn đặt xe"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_rejects_blank_turn_id(client):
    response = await client.post(
        "/api/v1/chat",
        json={"turn_id": "   ", "message": "Tôi muốn đặt xe"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert isinstance(data["llm_enabled"], bool)
    assert data["understanding_mode"] in {"openai", "rules"}
    assert data["conversation_backend"] == "core_agent"


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


@pytest.mark.asyncio
async def test_session_message_requires_valid_session(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/sessions/sess_missing/messages",
        json={"message": "Xin chào", "source": "TEXT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Authentication is valid; only the cached session id is stale/mismatched.
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_session_rebinds_token_without_logging_user_out(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    token = login.json()["access_token"]
    old_session_id = login.json()["session_id"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/sessions",
        json={"channel": "WEB_VOICE", "device_id": "browser"},
        headers=headers,
    )
    assert created.status_code == 201
    new_session_id = created.json()["session_id"]
    assert new_session_id != old_session_id

    stale = await client.get(f"/api/v1/sessions/{old_session_id}", headers=headers)
    current = await client.get(f"/api/v1/sessions/{new_session_id}", headers=headers)
    me = await client.get("/api/v1/auth/me", headers=headers)

    assert stale.status_code == 409
    assert current.status_code == 200
    assert me.status_code == 200
    assert me.json()["session_id"] == new_session_id


@pytest.mark.asyncio
async def test_session_message_requires_auth_header(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    session_id = login.json()["session_id"]

    response = await client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"message": "Xin chào", "source": "TEXT"},
    )
    assert response.status_code == 401
