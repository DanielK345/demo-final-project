from pydantic import BaseModel, Field


class RegisterRequestDTO(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequestDTO(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponseDTO(BaseModel):
    user_id: str
    full_name: str
    phone: str
    role: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    session_id: str


# `/auth/login` trả 1 trong 2 hình dạng thật tuỳ user có bật 2FA hay không: đăng nhập
# xong luôn (như AuthResponseDTO — mọi field bên dưới có giá trị, `requires_2fa` vắng/
# false) hoặc thử thách 2FA (chỉ `requires_2fa`+`pending_token` có giá trị, phần còn
# lại None — chưa phát access_token thật). Toàn bộ field optional để biểu diễn được cả
# 2 trường hợp bằng đúng 1 response_model, tránh Union phức tạp ở FastAPI.
class LoginResponseDTO(BaseModel):
    requires_2fa: bool = False
    pending_token: str | None = None
    user_id: str | None = None
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    session_id: str | None = None


class TwoFactorLoginVerifyRequestDTO(BaseModel):
    pending_token: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorSetupResponseDTO(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorConfirmRequestDTO(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorStatusDTO(BaseModel):
    two_factor_enabled: bool


class CurrentUserDTO(BaseModel):
    user_id: str
    full_name: str
    phone: str
    role: str
    session_id: str | None = None


class ChangePasswordRequestDTO(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
