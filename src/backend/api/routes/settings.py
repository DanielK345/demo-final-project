from fastapi import APIRouter, Header

from src.backend.api.routes.sessions import _user_id_from_header
from src.backend.schemas.settings import UpdateUserSettingsDTO, UserSettingsDTO
from src.backend.services.settings_service import SettingsService

router = APIRouter(prefix="/users/me/settings", tags=["settings"])
service = SettingsService()


@router.get("", response_model=UserSettingsDTO)
async def get_settings(authorization: str | None = Header(default=None)) -> UserSettingsDTO:
    user_id = _user_id_from_header(authorization)
    return UserSettingsDTO(**service.get_settings(user_id))


@router.put("", response_model=UserSettingsDTO)
async def update_settings(
    request: UpdateUserSettingsDTO,
    authorization: str | None = Header(default=None),
) -> UserSettingsDTO:
    user_id = _user_id_from_header(authorization)
    return UserSettingsDTO(**service.update_settings(user_id, request.model_dump()))
