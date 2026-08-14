_DEFAULTS: dict[str, object] = {
    "push_notifications": True,
    "email_notifications": False,
    "sms_notifications": True,
    "two_factor_enabled": False,
    "language": "vi",
    "theme": "light",
}


class SettingsService:
    settings_by_user: dict[str, dict[str, object]] = {}

    def get_settings(self, user_id: str) -> dict[str, object]:
        return {**_DEFAULTS, **self.settings_by_user.get(user_id, {})}

    def update_settings(self, user_id: str, updates: dict[str, object]) -> dict[str, object]:
        current = self.get_settings(user_id)
        current.update({key: value for key, value in updates.items() if value is not None})
        self.settings_by_user[user_id] = current
        return current
