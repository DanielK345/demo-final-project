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


class CurrentUserDTO(BaseModel):
    user_id: str
    full_name: str
    phone: str
    role: str
    session_id: str | None = None
