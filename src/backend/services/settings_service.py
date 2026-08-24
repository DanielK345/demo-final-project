from src.backend.config import get_settings
from src.backend.repositories.persistence_repository import PersistenceRepository

_DEFAULTS: dict[str, object] = {
    "push_notifications": True,
    "email_notifications": False,
    "sms_notifications": True,
    "two_factor_enabled": False,
    "language": "vi",
    "theme": "light",
}


class SettingsService:
    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()
        self._durable = get_settings().app_env != "test"

    async def get_settings_durable(self, user_id: str) -> dict[str, object]:
        if not self._durable:
            return self.get_settings(user_id)
        return await self._repository.get_settings(user_id)

    async def update_settings_durable(self, user_id: str, updates: dict[str, object]) -> dict[str, object]:
        if not self._durable:
            return self.update_settings(user_id, updates)
        return await self._repository.update_settings(user_id, updates)

    settings_by_user: dict[str, dict[str, object]] = {}

    def get_settings(self, user_id: str) -> dict[str, object]:
        return {**_DEFAULTS, **self.settings_by_user.get(user_id, {})}

    def update_settings(self, user_id: str, updates: dict[str, object]) -> dict[str, object]:
        current = self.get_settings(user_id)
        current.update({key: value for key, value in updates.items() if value is not None})
        self.settings_by_user[user_id] = current
        return current
