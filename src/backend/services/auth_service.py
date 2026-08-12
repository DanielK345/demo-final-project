from __future__ import annotations

from secrets import token_urlsafe
from uuid import uuid4

from src.backend.services.session_service import SessionService


class AuthService:
    """Small in-memory identity store for the MVP.

    Replace this adapter with a database/hashed-password provider before a
    production deployment. Keeping it here makes the web flow runnable with
    no external infrastructure.
    """

    users: dict[str, dict[str, str]] = {
        "0901234567": {
            "user_id": "usr_demo",
            "full_name": "Khách hàng AloSM",
            "phone": "0901234567",
            "password": "Password123!",
            "role": "CUSTOMER",
        }
    }
    tokens: dict[str, str] = {}
    token_sessions: dict[str, str] = {}
    _session_service = SessionService()

    def register(self, full_name: str, phone: str, password: str) -> dict[str, object]:
        if phone in self.users:
            raise ValueError("Số điện thoại đã được đăng ký")
        user = {
            "user_id": f"usr_{uuid4().hex[:10]}",
            "full_name": full_name,
            "phone": phone,
            "password": password,
            "role": "CUSTOMER",
        }
        self.users[phone] = user
        return self._auth_response(user)

    def login(self, phone: str, password: str) -> dict[str, object]:
        user = self.users.get(phone)
        if user is None or user["password"] != password:
            raise ValueError("Số điện thoại hoặc mật khẩu không đúng")
        return self._auth_response(user)

    def get_user_for_token(self, token: str) -> dict[str, str] | None:
        user_id = self.tokens.get(token)
        if not user_id:
            return None
        return next((user for user in self.users.values() if user["user_id"] == user_id), None)

    def get_session_for_token(self, token: str) -> str | None:
        return self.token_sessions.get(token)

    def bind_session_to_token(self, token: str, session_id: str) -> None:
        if token not in self.tokens:
            raise ValueError("Token không hợp lệ")
        self.token_sessions[token] = session_id

    def _auth_response(self, user: dict[str, str]) -> dict[str, object]:
        session = self._session_service.create_session(user["user_id"], "WEB_VOICE", "browser")
        token = self._issue_token(user["user_id"], session["session_id"])
        return {
            **self._public_user(user),
            "access_token": token,
            "expires_in": 3600,
            "session_id": session["session_id"],
        }

    def _issue_token(self, user_id: str, session_id: str) -> str:
        token = token_urlsafe(32)
        self.tokens[token] = user_id
        self.token_sessions[token] = session_id
        return token

    @staticmethod
    def _public_user(user: dict[str, str]) -> dict[str, str]:
        return {key: user[key] for key in ("user_id", "full_name", "phone", "role")}
