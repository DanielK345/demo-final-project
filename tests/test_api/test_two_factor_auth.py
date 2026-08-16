"""2FA (TOTP) thật — xem src/backend/services/auth_service.py.

Không mock pyotp: dùng đúng thư viện thật để sinh mã hợp lệ theo secret thật trả về
từ /auth/2fa/setup, giống hệt cách 1 app authenticator (Google Authenticator/Authy)
thật sự tính mã.
"""

import pyotp
import pytest


async def _register(client, phone: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "2FA Tester", "phone": phone, "password": "Password123!"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_login_without_2fa_is_unchanged(client):
    """User chưa bật 2FA — /auth/login vẫn trả access_token ngay, không có
    requires_2fa (hành vi cũ, không được phá vỡ bởi tính năng mới)."""
    user = await _register(client, "0911000001")
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0911000001", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("requires_2fa") in (False, None)
    assert data["access_token"]
    assert data["user_id"] == user["user_id"]


@pytest.mark.asyncio
async def test_setup_confirm_and_enforce_login(client):
    user = await _register(client, "0911000002")
    token = user["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Bật 2FA — lấy secret thật
    setup = await client.post("/api/v1/auth/2fa/setup", headers=auth_header)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_url"].startswith("otpauth://totp/")

    # 2. Mã sai -> 400, chưa bật
    bad_confirm = await client.post(
        "/api/v1/auth/2fa/confirm", json={"code": "000000"}, headers=auth_header
    )
    assert bad_confirm.status_code == 400

    # 3. Mã đúng (tính thật từ secret, như 1 app authenticator thật) -> bật thành công
    valid_code = pyotp.TOTP(secret).now()
    confirm = await client.post(
        "/api/v1/auth/2fa/confirm", json={"code": valid_code}, headers=auth_header
    )
    assert confirm.status_code == 200
    assert confirm.json()["two_factor_enabled"] is True

    # 4. GET settings phản ánh đúng trạng thái thật
    settings = await client.get("/api/v1/users/me/settings", headers=auth_header)
    assert settings.status_code == 200
    assert settings.json()["two_factor_enabled"] is True

    # 5. Đăng nhập lại -> KHÔNG còn nhận access_token ngay, phải qua bước 2 (thử mật
    # khẩu lộ ra vẫn không đăng nhập được nếu không có app authenticator thật)
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0911000002", "password": "Password123!"},
    )
    assert login.status_code == 200
    login_data = login.json()
    assert login_data["requires_2fa"] is True
    assert login_data["access_token"] is None
    pending_token = login_data["pending_token"]
    assert pending_token

    # 6. Mã sai ở bước xác thực đăng nhập -> 401, không lộ access_token
    bad_verify = await client.post(
        "/api/v1/auth/2fa/verify-login",
        json={"pending_token": pending_token, "code": "000000"},
    )
    assert bad_verify.status_code == 401

    # 7. Mã đúng -> hoàn tất đăng nhập, nhận access_token thật
    good_code = pyotp.TOTP(secret).now()
    verify = await client.post(
        "/api/v1/auth/2fa/verify-login",
        json={"pending_token": pending_token, "code": good_code},
    )
    assert verify.status_code == 200
    verify_data = verify.json()
    assert verify_data["access_token"]
    assert verify_data["user_id"] == user["user_id"]


@pytest.mark.asyncio
async def test_disable_two_factor_restores_direct_login(client):
    user = await _register(client, "0911000003")
    auth_header = {"Authorization": f"Bearer {user['access_token']}"}

    setup = await client.post("/api/v1/auth/2fa/setup", headers=auth_header)
    secret = setup.json()["secret"]
    await client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=auth_header,
    )

    disable = await client.post("/api/v1/auth/2fa/disable", headers=auth_header)
    assert disable.status_code == 200
    assert disable.json()["two_factor_enabled"] is False

    login = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0911000003", "password": "Password123!"},
    )
    assert login.status_code == 200
    assert login.json().get("requires_2fa") in (False, None)
    assert login.json()["access_token"]


@pytest.mark.asyncio
async def test_verify_login_rejects_unknown_pending_token(client):
    response = await client.post(
        "/api/v1/auth/2fa/verify-login",
        json={"pending_token": "does-not-exist", "code": "123456"},
    )
    assert response.status_code == 401
