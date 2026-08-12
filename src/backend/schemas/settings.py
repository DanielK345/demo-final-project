from pydantic import BaseModel


class UserSettingsDTO(BaseModel):
    push_notifications: bool = True
    email_notifications: bool = False
    sms_notifications: bool = True
    # Lưu ý: toggle này chỉ PERSIST lựa chọn, CHƯA enforce thật ở bước đăng nhập (cần
    # TOTP/SMS provider — xem mustdo.md mục 4). Không giả vờ đã bảo mật hơn thật.
    two_factor_enabled: bool = False
    language: str = "vi"
    theme: str = "light"


class UpdateUserSettingsDTO(BaseModel):
    push_notifications: bool | None = None
    email_notifications: bool | None = None
    sms_notifications: bool | None = None
    two_factor_enabled: bool | None = None
    language: str | None = None
    theme: str | None = None
