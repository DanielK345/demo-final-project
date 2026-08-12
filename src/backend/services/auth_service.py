from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from secrets import token_hex, token_urlsafe
from uuid import uuid4

from src.backend.services.session_service import SessionService

# PBKDF2-HMAC-SHA256, stdlib-only (không thêm dependency mới như bcrypt/passlib) —
# đủ an toàn cho MVP in-memory này và tránh rủi ro cài đặt package trong môi trường
# chưa biết. 260_000 vòng lặp theo khuyến nghị OWASP/Django hiện tại.
_PBKDF2_ITERATIONS = 260_000
_TOKEN_TTL_SECONDS = 3600


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split("$", 1)
    except ValueError:
        return False
    # so sánh hằng-thời-gian (constant-time) để tránh timing attack
    return hmac.compare_digest(_hash_password(password, salt), stored_hash)


class AuthService:
    """Small in-memory identity store for the MVP.

    Replace this adapter with a database provider before a production
    deployment (xem `mustdo.md`). Keeping it here makes the web flow runnable
    with no external infrastructure. Mật khẩu KHÔNG lưu plaintext — hash bằng
    PBKDF2-HMAC-SHA256 + salt riêng cho từng user (xem `_hash_password`).
    """

    users: dict[str, dict[str, str]] = {
        "0901234567": {
            "user_id": "usr_demo",
            "full_name": "Khách hàng AloSM",
            "phone": "0901234567",
            "password_hash": _hash_password("Password123!"),
            "role": "CUSTOMER",
        }
    }
    # token -> {"user_id", "session_id", "issued_at"} — TTL enforce ở _is_expired.
    tokens: dict[str, dict[str, object]] = {}
    _session_service = SessionService()

    def register(self, full_name: str, phone: str, password: str) -> dict[str, object]:
        if phone in self.users:
            raise ValueError("Số điện thoại đã được đăng ký")
        user = {
            "user_id": f"usr_{uuid4().hex[:10]}",
            "full_name": full_name,
            "phone": phone,
            "password_hash": _hash_password(password),
            "role": "CUSTOMER",
        }
        self.users[phone] = user
        return self._auth_response(user)

    def login(self, phone: str, password: str) -> dict[str, object]:
        user = self.users.get(phone)
        if user is None or not _verify_password(password, user["password_hash"]):
            raise ValueError("Số điện thoại hoặc mật khẩu không đúng")
        return self._auth_response(user)

    def get_user_for_token(self, token: str) -> dict[str, str] | None:
        record = self.tokens.get(token)
        if record is None:
            return None
        if self._is_expired(record):
            del self.tokens[token]
            return None
        return next((user for user in self.users.values() if user["user_id"] == record["user_id"]), None)

    def get_session_for_token(self, token: str) -> str | None:
        record = self.tokens.get(token)
        if record is None or self._is_expired(record):
            return None
        return record["session_id"]  # type: ignore[return-value]

    def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        user = next((u for u in self.users.values() if u["user_id"] == user_id), None)
        if user is None:
            raise ValueError("Không tìm thấy người dùng")
        if not _verify_password(old_password, user["password_hash"]):
            raise ValueError("Mật khẩu hiện tại không đúng")
        user["password_hash"] = _hash_password(new_password)

    @staticmethod
    def _is_expired(record: dict[str, object]) -> bool:
        issued_at = record["issued_at"]
        assert isinstance(issued_at, datetime)
        return datetime.now(UTC) - issued_at > timedelta(seconds=_TOKEN_TTL_SECONDS)

    def bind_session_to_token(self, token: str, session_id: str) -> None:
        record = self.tokens.get(token)
        if record is None:
            raise ValueError("Token không hợp lệ")
        record["session_id"] = session_id

    def _auth_response(self, user: dict[str, str]) -> dict[str, object]:
        session = self._session_service.create_session(user["user_id"], "WEB_VOICE", "browser")
        token = self._issue_token(user["user_id"], session["session_id"])
        return {
            **self._public_user(user),
            "access_token": token,
            "expires_in": _TOKEN_TTL_SECONDS,
            "session_id": session["session_id"],
        }

    def _issue_token(self, user_id: str, session_id: str) -> str:
        token = token_urlsafe(32)
        self.tokens[token] = {"user_id": user_id, "session_id": session_id, "issued_at": datetime.now(UTC)}
        return token

    @staticmethod
    def _public_user(user: dict[str, str]) -> dict[str, str]:
        return {key: user[key] for key in ("user_id", "full_name", "phone", "role")}
