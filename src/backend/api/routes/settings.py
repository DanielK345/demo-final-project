from fastapi import APIRouter, Header

from src.backend.api.routes.sessions import _user_from_header, _user_id_from_header
from src.backend.schemas.settings import UpdateUserSettingsDTO, UserSettingsDTO
from src.backend.services.settings_service import SettingsService

router = APIRouter(prefix="/users/me/settings", tags=["settings"])
service = SettingsService()


@router.get("", response_model=UserSettingsDTO)
async def get_settings(authorization: str | None = Header(default=None)) -> UserSettingsDTO:
    user = await _user_from_header(authorization)
    data = await service.get_settings_durable(str(user["user_id"]))
    # two_factor_enabled thật nằm ở AuthService (bật/tắt qua /auth/2fa/*), không phải
    # SettingsService — ghi đè lại đây để GET luôn phản ánh đúng trạng thái thật.
    data["two_factor_enabled"] = bool(user.get("two_factor_enabled"))
    return UserSettingsDTO(**data)


@router.put("", response_model=UserSettingsDTO)
async def update_settings(
    request: UpdateUserSettingsDTO,
    authorization: str | None = Header(default=None),
) -> UserSettingsDTO:
    user_id = await _user_id_from_header(authorization)
    return UserSettingsDTO(**await service.update_settings_durable(user_id, request.model_dump()))
