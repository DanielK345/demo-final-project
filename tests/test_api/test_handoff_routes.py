import pytest

from src.backend.services.auth_service import AuthService


async def _login(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Password123!"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_handoff_routes_require_auth_and_operator_role(client):
    unauthenticated = await client.get("/api/v1/handoffs")
    assert unauthenticated.status_code == 401

    login = await _login(client)
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    created = await client.post(
        "/api/v1/handoffs",
        headers=headers,
        json={
            "session_id": login["session_id"],
            "reason": "Customer requested support",
            "reason_code": "USER_REQUEST",
            "summary": "Safe summary",
        },
    )
    assert created.status_code == 201

    forbidden = await client.get("/api/v1/handoffs", headers=headers)
    assert forbidden.status_code == 403

    AuthService.users["0901234567"]["role"] = "OPERATOR"
    try:
        pending = await client.get("/api/v1/handoffs", headers=headers)
        assert pending.status_code == 200
        handoff_id = created.json()["handoff_id"]
        assert any(item["handoff_id"] == handoff_id for item in pending.json())

        accepted = await client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=headers)
        assert accepted.status_code == 200
        assert accepted.json()["operator_id"] == "usr_demo"
    finally:
        AuthService.users["0901234567"]["role"] = "CUSTOMER"


@pytest.mark.asyncio
async def test_customer_cannot_create_handoff_for_another_session(client):
    login = await _login(client)
    response = await client.post(
        "/api/v1/handoffs",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={
            "session_id": "sess-other",
            "reason": "Invalid ownership",
            "summary": "Safe summary",
        },
    )

    assert response.status_code == 403
