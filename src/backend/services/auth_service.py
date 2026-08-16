from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from secrets import token_hex, token_urlsafe
from uuid import uuid4

import pyotp

from src.backend.config import get_settings
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.services.field_crypto import FieldCipher
from src.backend.services.policy_service import PolicyService
from src.backend.services.session_service import SessionService

# PBKDF2-HMAC-SHA256, stdlib-only (không thêm dependency mới như bcrypt/passlib) —
# đủ an toàn cho MVP in-memory này và tránh rủi ro cài đặt package trong môi trường
# chưa biết. 260_000 vòng lặp theo khuyến nghị OWASP/Django hiện tại.
_PBKDF2_ITERATIONS = 260_000
_TOKEN_TTL_SECONDS = 3600

# 2FA (TOTP, RFC 6238) — `pyotp` là thư viện thuần Python, không cần dịch vụ ngoài
# (SMS/email provider), đúng gợi ý đã ghi ở mustdo.md mục 4. Token xác thực bước 2 lúc
# đăng nhập (`pending_2fa`) có TTL riêng, ngắn hơn access token thật — chỉ dùng đúng 1
# lần để hoàn tất đăng nhập, không phải access token.
_PENDING_2FA_TTL_SECONDS = 300
_TOTP_ISSUER = "AloSM"


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
    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()
        self._cipher = FieldCipher()
        self._durable = get_settings().app_env != "test"

    async def register_durable(
        self,
        full_name: str,
        phone: str,
        password: str,
        accepted_terms_version: str,
        accepted_privacy_version: str,
    ) -> dict[str, object]:
        if not self._durable:
            return self.register(full_name, phone, password, accepted_terms_version, accepted_privacy_version)
        self._policy_service.assert_acceptance(terms_version=accepted_terms_version, privacy_version=accepted_privacy_version)
        user = await self._repository.create_user(
            full_name=full_name, phone=phone, password_hash=_hash_password(password),
            terms_version=accepted_terms_version, privacy_version=accepted_privacy_version,
            source_sha256=self._policy_service.catalog.source_sha256,
        )
        return await self._auth_response_durable(user)

    async def login_durable(self, phone: str, password: str) -> dict[str, object]:
        if not self._durable:
            return self.login(phone, password)
        user = await self._repository.user_by_phone(phone)
        if user is None or not _verify_password(password, str(user["password_hash"])):
            raise ValueError("Số điện thoại hoặc mật khẩu không đúng")
        if user.get("two_factor_enabled"):
            pending_token = token_urlsafe(24)
            await self._repository.create_auth_challenge(
                raw_token=pending_token, user_id=str(user["user_id"]),
                expires_at=datetime.now(UTC) + timedelta(seconds=_PENDING_2FA_TTL_SECONDS),
            )
            return {"requires_2fa": True, "pending_token": pending_token}
        return await self._auth_response_durable(user)

    async def verify_login_two_factor_durable(self, pending_token: str, code: str) -> dict[str, object]:
        if not self._durable:
            return self.verify_login_two_factor(pending_token, code)
        user = await self._repository.auth_challenge_user(pending_token)
        if user is None:
            raise ValueError("Yêu cầu xác thực đã hết hạn. Vui lòng đăng nhập lại.")
        secret = self._cipher.decrypt(user.get("totp_secret_ciphertext") if isinstance(user.get("totp_secret_ciphertext"), str) else None)
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise ValueError("Mã xác thực không đúng")
        consumed = await self._repository.consume_auth_challenge(pending_token)
        if consumed is None:
            raise ValueError("Yêu cầu xác thực đã được sử dụng.")
        return await self._auth_response_durable(consumed)

    async def enable_two_factor_setup_durable(self, user_id: str) -> dict[str, str]:
        if not self._durable:
            return self.enable_two_factor_setup(user_id)
        user = await self._repository.user_by_id(user_id)
        if user is None:
            raise ValueError("Không tìm thấy người dùng")
        secret = pyotp.random_base32()
        await self._repository.update_user_security(user_id, totp_pending_secret_ciphertext=self._cipher.encrypt(secret))
        return {"secret": secret, "otpauth_url": pyotp.TOTP(secret).provisioning_uri(name=str(user["phone"]), issuer_name=_TOTP_ISSUER)}

    async def confirm_two_factor_durable(self, user_id: str, code: str) -> None:
        if not self._durable:
            self.confirm_two_factor(user_id, code)
            return
        user = await self._repository.user_by_id(user_id)
        encrypted = user.get("totp_pending_secret_ciphertext") if user else None
        secret = self._cipher.decrypt(encrypted if isinstance(encrypted, str) else None)
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise ValueError("Mã xác thực không đúng hoặc đã hết hạn — hãy bật lại 2FA để lấy mã mới.")
        await self._repository.update_user_security(user_id, totp_secret_ciphertext=self._cipher.encrypt(secret), totp_pending_secret_ciphertext=None, two_factor_enabled=True)

    async def disable_two_factor_durable(self, user_id: str) -> None:
        if not self._durable:
            self.disable_two_factor(user_id)
            return
        await self._repository.update_user_security(user_id, totp_secret_ciphertext=None, totp_pending_secret_ciphertext=None, two_factor_enabled=False)

    async def get_user_for_token_durable(self, token: str) -> dict[str, object] | None:
        if not self._durable:
            return self.get_user_for_token(token)
        return await self._repository.user_for_token(token)

    async def get_session_for_token_durable(self, token: str) -> str | None:
        if not self._durable:
            return self.get_session_for_token(token)
        return await self._repository.session_for_token(token)

    async def bind_session_to_token_durable(self, token: str, session_id: str) -> None:
        if not self._durable:
            self.bind_session_to_token(token, session_id)
            return
        await self._repository.bind_token_session(token, session_id)

    async def change_password_durable(self, user_id: str, old_password: str, new_password: str) -> None:
        if not self._durable:
            self.change_password(user_id, old_password, new_password)
            return
        user = await self._repository.user_by_id(user_id)
        if user is None or not _verify_password(old_password, str(user["password_hash"])):
            raise ValueError("Mật khẩu hiện tại không đúng")
        await self._repository.update_user_security(user_id, password_hash=_hash_password(new_password), password_changed_at=datetime.now(UTC))

    async def _auth_response_durable(self, user: dict[str, object]) -> dict[str, object]:
        session = await self._session_service.create_session_durable(str(user["user_id"]), "WEB_VOICE", "browser", phone=str(user["phone"]))
        token = token_urlsafe(32)
        await self._repository.issue_token(raw_token=token, user_id=str(user["user_id"]), session_id=str(session["session_id"]), expires_at=datetime.now(UTC) + timedelta(seconds=_TOKEN_TTL_SECONDS))
        return {**self._public_user(user), "access_token": token, "expires_in": _TOKEN_TTL_SECONDS, "session_id": session["session_id"]}
    """Small in-memory identity store for the MVP.

    Replace this adapter with a database provider before a production
    deployment (xem `mustdo.md`). Keeping it here makes the web flow runnable
    with no external infrastructure. Mật khẩu KHÔNG lưu plaintext — hash bằng
    PBKDF2-HMAC-SHA256 + salt riêng cho từng user (xem `_hash_password`).
    """

    # Giá trị dict[str, object] (không còn thuần dict[str, str]) kể từ khi thêm field
    # 2FA (`two_factor_enabled: bool`, `totp_secret`/`totp_pending_secret: str | None`).
    users: dict[str, dict[str, object]] = {
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
    # pending_token -> {"user_id", "issued_at"} — bước trung gian giữa "mật khẩu đúng"
    # và "đăng nhập xong" khi user đã bật 2FA; KHÔNG phải access token (không mở được
    # bất kỳ endpoint nào khác ngoài verify_login_two_factor), TTL ngắn hơn nhiều.
    pending_2fa: dict[str, dict[str, object]] = {}
    _session_service = SessionService()
    _policy_service = PolicyService()

    def register(
        self,
        full_name: str,
        phone: str,
        password: str,
        accepted_terms_version: str,
        accepted_privacy_version: str,
    ) -> dict[str, object]:
        self._policy_service.assert_acceptance(
            terms_version=accepted_terms_version,
            privacy_version=accepted_privacy_version,
        )
        if phone in self.users:
            raise ValueError("Số điện thoại đã được đăng ký")
        user = {
            "user_id": f"usr_{uuid4().hex[:10]}",
            "full_name": full_name,
            "phone": phone,
            "password_hash": _hash_password(password),
            "role": "CUSTOMER",
            "policy_acceptance": {
                "terms_version": accepted_terms_version,
                "privacy_version": accepted_privacy_version,
                "accepted_at": datetime.now(UTC).isoformat(),
                "source_sha256": self._policy_service.catalog.source_sha256,
            },
        }
        self.users[phone] = user
        return self._auth_response(user)

    def login(self, phone: str, password: str) -> dict[str, object]:
        user = self.users.get(phone)
        if user is None or not _verify_password(password, user["password_hash"]):
            raise ValueError("Số điện thoại hoặc mật khẩu không đúng")
        if user.get("two_factor_enabled"):
            # Mật khẩu đúng nhưng CHƯA đăng nhập xong — trả về 1 token tạm để hoàn tất
            # bằng mã TOTP (xem verify_login_two_factor). Không phát access_token thật
            # ở bước này.
            pending_token = token_urlsafe(24)
            self.pending_2fa[pending_token] = {"user_id": user["user_id"], "issued_at": datetime.now(UTC)}
            return {"requires_2fa": True, "pending_token": pending_token}
        return self._auth_response(user)

    def verify_login_two_factor(self, pending_token: str, code: str) -> dict[str, object]:
        record = self.pending_2fa.get(pending_token)
        if record is not None and self._pending_2fa_expired(record):
            del self.pending_2fa[pending_token]
            record = None
        if record is None:
            raise ValueError("Yêu cầu xác thực đã hết hạn. Vui lòng đăng nhập lại.")
        user = self._find_user(str(record["user_id"]))
        secret = user.get("totp_secret")
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise ValueError("Mã xác thực không đúng")
        del self.pending_2fa[pending_token]
        return self._auth_response(user)

    def enable_two_factor_setup(self, user_id: str) -> dict[str, str]:
        """Tạo secret TOTP mới (CHƯA bật) — chờ confirm_two_factor() xác nhận đúng 1 mã
        thật từ app authenticator trước khi thật sự bật, để tránh tự khoá tài khoản
        bằng 1 secret chưa từng verify được (vd cấu hình sai lúc quét/nhập)."""
        user = self._find_user(user_id)
        secret = pyotp.random_base32()
        user["totp_pending_secret"] = secret
        otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(name=user["phone"], issuer_name=_TOTP_ISSUER)
        return {"secret": secret, "otpauth_url": otpauth_url}

    def confirm_two_factor(self, user_id: str, code: str) -> None:
        user = self._find_user(user_id)
        pending_secret = user.get("totp_pending_secret")
        if not pending_secret or not pyotp.TOTP(pending_secret).verify(code, valid_window=1):
            raise ValueError("Mã xác thực không đúng hoặc đã hết hạn — hãy bật lại 2FA để lấy mã mới.")
        user["totp_secret"] = pending_secret
        user["totp_pending_secret"] = None
        user["two_factor_enabled"] = True

    def disable_two_factor(self, user_id: str) -> None:
        user = self._find_user(user_id)
        user["totp_secret"] = None
        user["totp_pending_secret"] = None
        user["two_factor_enabled"] = False

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
        user = self._find_user(user_id)
        if not _verify_password(old_password, user["password_hash"]):
            raise ValueError("Mật khẩu hiện tại không đúng")
        user["password_hash"] = _hash_password(new_password)

    def _find_user(self, user_id: str) -> dict[str, object]:
        user = next((u for u in self.users.values() if u["user_id"] == user_id), None)
        if user is None:
            raise ValueError("Không tìm thấy người dùng")
        return user

    @staticmethod
    def _is_expired(record: dict[str, object]) -> bool:
        issued_at = record["issued_at"]
        assert isinstance(issued_at, datetime)
        return datetime.now(UTC) - issued_at > timedelta(seconds=_TOKEN_TTL_SECONDS)

    @staticmethod
    def _pending_2fa_expired(record: dict[str, object]) -> bool:
        issued_at = record["issued_at"]
        assert isinstance(issued_at, datetime)
        return datetime.now(UTC) - issued_at > timedelta(seconds=_PENDING_2FA_TTL_SECONDS)

    def bind_session_to_token(self, token: str, session_id: str) -> None:
        record = self.tokens.get(token)
        if record is None:
            raise ValueError("Token không hợp lệ")
        record["session_id"] = session_id

    def _auth_response(self, user: dict[str, object]) -> dict[str, object]:
        session = self._session_service.create_session(
            user["user_id"], "WEB_VOICE", "browser", phone=user.get("phone")
        )
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
    def _public_user(user: dict[str, object]) -> dict[str, str]:
        return {key: str(user[key]) for key in ("user_id", "full_name", "phone", "role")}
