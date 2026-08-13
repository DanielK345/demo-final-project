import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


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
