from fastapi import APIRouter, Header, HTTPException, status

from src.backend.schemas.auth import AuthResponseDTO, CurrentUserDTO, LoginRequestDTO, RegisterRequestDTO
from src.backend.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
service = AuthService()


@router.post("/register", response_model=AuthResponseDTO, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequestDTO) -> AuthResponseDTO:
    try:
        return AuthResponseDTO(**service.register(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponseDTO)
async def login(request: LoginRequestDTO) -> AuthResponseDTO:
    try:
        return AuthResponseDTO(**service.login(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/me", response_model=CurrentUserDTO)
async def me(authorization: str | None = Header(default=None)) -> CurrentUserDTO:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = service.get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ")
    return CurrentUserDTO(**AuthService._public_user(user), session_id=service.get_session_for_token(token))
