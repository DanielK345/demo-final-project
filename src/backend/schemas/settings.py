from pydantic import BaseModel


class UserSettingsDTO(BaseModel):
    push_notifications: bool = True
    email_notifications: bool = False
    sms_notifications: bool = True
    # Giá trị THẬT lấy từ AuthService (TOTP thật đã enforce ở bước đăng nhập — xem
    # src/backend/api/routes/auth.py mục 2fa/*), không phải cờ trang trí nữa. Route
    # GET tự ghi đè field này bằng trạng thái thật trước khi trả về (xem settings.py).
    two_factor_enabled: bool = False
    language: str = "vi"
    theme: str = "light"


class UpdateUserSettingsDTO(BaseModel):
    push_notifications: bool | None = None
    email_notifications: bool | None = None
    sms_notifications: bool | None = None
    # two_factor_enabled KHÔNG còn set được qua PUT chung này — phải qua đúng luồng
    # thật /auth/2fa/setup + /auth/2fa/confirm (bật) hoặc /auth/2fa/disable (tắt), để
    # không thể "bật" 2FA mà chưa từng xác thực được 1 mã TOTP thật nào.
    language: str | None = None
    theme: str | None = None
