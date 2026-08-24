import pytest


@pytest.mark.asyncio
async def test_current_policy_and_source_are_public_and_consistent(client):
    catalog_response = await client.get("/api/v1/policies/current")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["catalog_version"] == "2026-08-16"
    assert catalog["status"] == "APPROVED_PROJECT_POLICY"
    assert catalog["operational_rules"]

    source_response = await client.get(catalog["source_endpoint"])
    assert source_response.status_code == 200
    source = source_response.json()
    assert source["sha256"] == catalog["source_sha256"]
    assert "ĐIỀU KHOẢN SỬ DỤNG" in source["content"]


@pytest.mark.asyncio
async def test_registration_requires_current_policy_versions_and_exposes_acceptance(client):
    missing = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Policy Tester", "phone": "0911777001", "password": "Password123!"},
    )
    assert missing.status_code == 422

    stale = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Policy Tester",
            "phone": "0911777002",
            "password": "Password123!",
            "accepted_terms_version": "old",
            "accepted_privacy_version": "2026-08-16",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "POLICY_VERSION_MISMATCH"

    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Policy Tester",
            "phone": "0911777003",
            "password": "Password123!",
            "accepted_terms_version": "2026-08-16",
            "accepted_privacy_version": "2026-08-16",
        },
    )
    assert registered.status_code == 201
    token = registered.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    acceptance = me.json()["policy_acceptance"]
    assert acceptance["terms_version"] == "2026-08-16"
    assert acceptance["privacy_version"] == "2026-08-16"
    assert acceptance["accepted_at"]
    assert acceptance["source_sha256"] == "5954A5851773F70BA8E5E81AD3785EAA662B86FED5DB7FE38089BC99270F791B"
