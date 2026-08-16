from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.backend.config import Settings, get_settings


class FieldCipher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _fernet(self) -> Fernet:
        secret = self.settings.field_encryption_key
        if not secret:
            if self.settings.app_env == "production":
                raise RuntimeError("FIELD_ENCRYPTION_KEY_REQUIRED")
            secret = f"{self.settings.app_name}:development-field-key"
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)

    def encrypt(self, value: str | None) -> str | None:
        return self._fernet().encrypt(value.encode()).decode() if value else None

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("FIELD_DECRYPTION_FAILED") from exc
