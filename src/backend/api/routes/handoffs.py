from fastapi import APIRouter, Header, HTTPException, Query, status

from src.backend.api.routes.auth import service as auth_service
from src.backend.controllers.handoff_controller import HandoffController
from src.backend.schemas.handoff import HandoffAcceptanceDTO, HandoffDTO, HandoffResponseDTO
from src.backend.services.session_service import SessionService

router = APIRouter(prefix="/handoffs", tags=["handoffs"])
controller = HandoffController()


async def _authenticated_user(authorization: str | None) -> dict[str, object]:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = await auth_service.get_user_for_token_durable(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Yêu cầu xác thực")
    return user


async def _require_operator(authorization: str | None) -> dict[str, object]:
    user = await _authenticated_user(authorization)
    if user.get("role") not in {"OPERATOR", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ tổng đài viên được truy cập")
    return user


@router.post("", response_model=HandoffResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_handoff(
    request: HandoffDTO,
    authorization: str | None = Header(default=None),
) -> HandoffResponseDTO:
    user = await _authenticated_user(authorization)
    try:
        session = await SessionService().get_session_durable(request.session_id)
    except KeyError:
        session = None
    if session is None or session.get("user_id") != user.get("user_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền với phiên này")
    return await controller.create_handoff(request)


@router.get("", response_model=list[HandoffResponseDTO])
async def list_pending_handoffs(
    handoff_status: str = Query(default="pending", alias="status"),
    authorization: str | None = Header(default=None),
) -> list[HandoffResponseDTO]:
    await _require_operator(authorization)
    try:
        return await controller.list_handoffs(handoff_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Trạng thái handoff không hợp lệ") from exc


@router.post("/{handoff_id}/accept", response_model=HandoffAcceptanceDTO)
async def accept_handoff(
    handoff_id: str,
    authorization: str | None = Header(default=None),
) -> HandoffAcceptanceDTO:
    operator = await _require_operator(authorization)
    try:
        return await controller.accept_handoff(handoff_id, operator.get("user_id"))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
