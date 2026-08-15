from fastapi import APIRouter, Header, HTTPException, status

from src.backend.schemas.auth import (
    AuthResponseDTO,
    ChangePasswordRequestDTO,
    CurrentUserDTO,
    LoginRequestDTO,
    LoginResponseDTO,
    RegisterRequestDTO,
    TwoFactorConfirmRequestDTO,
    TwoFactorLoginVerifyRequestDTO,
    TwoFactorSetupResponseDTO,
    TwoFactorStatusDTO,
)
from src.backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
service = AuthService()

_SESSION_AUTH_MESSAGE = "Phiên đăng nhập không hợp lệ"


def _authenticated_user(authorization: str | None) -> dict[str, object]:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = service.get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_AUTH_MESSAGE)
    return user


@router.post("/register", response_model=AuthResponseDTO, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequestDTO) -> AuthResponseDTO:
    try:
        return AuthResponseDTO(**service.register(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=LoginResponseDTO)
async def login(request: LoginRequestDTO) -> LoginResponseDTO:
    """Trả `AuthResponseDTO` đầy đủ nếu user chưa bật 2FA (hành vi cũ, không đổi).
    Nếu đã bật 2FA thật (xem `/auth/2fa/*`), trả `requires_2fa=true` +
    `pending_token` — client phải gọi tiếp `/auth/2fa/verify-login` với mã TOTP thật
    từ app authenticator mới nhận được access_token."""
    try:
        return LoginResponseDTO(**service.login(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/2fa/verify-login", response_model=AuthResponseDTO)
async def verify_login_two_factor(request: TwoFactorLoginVerifyRequestDTO) -> AuthResponseDTO:
    try:
        return AuthResponseDTO(**service.verify_login_two_factor(request.pending_token, request.code))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/2fa/setup", response_model=TwoFactorSetupResponseDTO)
async def setup_two_factor(authorization: str | None = Header(default=None)) -> TwoFactorSetupResponseDTO:
    """Tạo secret TOTP mới cho user đã đăng nhập — CHƯA bật 2FA thật, chỉ bật sau khi
    `/auth/2fa/confirm` xác nhận đúng 1 mã thật (tránh tự khoá tài khoản bằng secret
    chưa từng verify)."""
    user = _authenticated_user(authorization)
    return TwoFactorSetupResponseDTO(**service.enable_two_factor_setup(str(user["user_id"])))


@router.post("/2fa/confirm", response_model=TwoFactorStatusDTO)
async def confirm_two_factor(
    request: TwoFactorConfirmRequestDTO,
    authorization: str | None = Header(default=None),
) -> TwoFactorStatusDTO:
    user = _authenticated_user(authorization)
    try:
        service.confirm_two_factor(str(user["user_id"]), request.code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TwoFactorStatusDTO(two_factor_enabled=True)


@router.post("/2fa/disable", response_model=TwoFactorStatusDTO)
async def disable_two_factor(authorization: str | None = Header(default=None)) -> TwoFactorStatusDTO:
    user = _authenticated_user(authorization)
    service.disable_two_factor(str(user["user_id"]))
    return TwoFactorStatusDTO(two_factor_enabled=False)


@router.get("/me", response_model=CurrentUserDTO)
async def me(authorization: str | None = Header(default=None)) -> CurrentUserDTO:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = service.get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_AUTH_MESSAGE)
    return CurrentUserDTO(**AuthService._public_user(user), session_id=service.get_session_for_token(token))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequestDTO,
    authorization: str | None = Header(default=None),
) -> None:
    user = _authenticated_user(authorization)
    try:
        service.change_password(str(user["user_id"]), request.old_password, request.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
