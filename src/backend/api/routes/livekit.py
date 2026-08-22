"""Authenticated LiveKit TokenSource endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from src.backend.api.routes.auth import service as auth_service
from src.backend.schemas.livekit import (
    LiveKitOperatorTokenRequestDTO,
    LiveKitOperatorTokenResponseDTO,
    LiveKitPrepareRequestDTO,
    LiveKitPrepareResponseDTO,
    LiveKitTokenRequestDTO,
    LiveKitTokenResponseDTO,
)
from src.backend.services.handoff_service import HandoffService
from src.backend.services.livekit_service import LiveKitTokenService, get_livekit_token_service
from src.backend.services.session_service import SessionService

router = APIRouter(prefix="/livekit", tags=["livekit"])
handoff_service = HandoffService()


async def _authenticated_call_owner(authorization: str | None) -> tuple[str, str]:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = await auth_service.get_user_for_token_durable(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để bắt đầu cuộc gọi",
        )
    app_session_id = await auth_service.get_session_for_token_durable(token)
    if not app_session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chưa có phiên hội thoại AloSM đang hoạt động",
        )
    try:
        app_session = await SessionService().get_session_durable(app_session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phiên hội thoại không còn tồn tại; hãy bắt đầu phiên mới",
        ) from exc
    if app_session.get("status") != "ACTIVE" or app_session.get("voice_session_terminal"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phiên hội thoại đã kết thúc; hãy bắt đầu phiên mới",
        )
    return str(user["user_id"]), app_session_id


def _validated_call_instance(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định danh cuộc gọi AloSM không hợp lệ",
        ) from exc


@router.post(
    "/prepare",
    response_model=LiveKitPrepareResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_livekit_call(
    request: LiveKitPrepareRequestDTO,
    authorization: str | None = Header(default=None),
    token_service: LiveKitTokenService = Depends(get_livekit_token_service),
) -> LiveKitPrepareResponseDTO:
    """Create and dispatch an opaque Room before the browser finishes mounting."""

    user_id, app_session_id = await _authenticated_call_owner(authorization)
    call_instance_id = _validated_call_instance(request.call_instance_id)
    try:
        prepared = await token_service.prepare_for_user(
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_instance_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LiveKit chưa được cấu hình sẵn sàng",
        ) from exc
    return LiveKitPrepareResponseDTO(
        server_url=prepared.details.server_url,
        participant_token=prepared.details.participant_token,
        agent_prepared=prepared.agent_prepared,
    )


@router.post(
    "/token",
    response_model=LiveKitTokenResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_livekit_token(
    request: LiveKitTokenRequestDTO,
    authorization: str | None = Header(default=None),
    token_service: LiveKitTokenService = Depends(get_livekit_token_service),
) -> LiveKitTokenResponseDTO:
    """Return standard LiveKit connection details using server-owned identity fields."""

    user_id, app_session_id = await _authenticated_call_owner(authorization)

    # Identity, room, metadata and deployment are security boundaries. The client
    # may request only the one agent name configured by the server.
    forbidden_values = (
        request.room_name,
        request.participant_name,
        request.participant_identity,
        request.participant_metadata,
        request.agent_metadata,
        request.deployment,
    )
    if any(forbidden_values):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LiveKit room và participant được máy chủ AloSM quản lý",
        )
    if request.agent_name and request.agent_name != token_service.agent_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LiveKit agent không hợp lệ",
        )

    attributes = request.participant_attributes or {}
    if set(attributes) != {"alosm.call_id"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu định danh cuộc gọi AloSM",
        )
    call_instance_id = _validated_call_instance(attributes["alosm.call_id"])

    try:
        details = token_service.issue_for_user(
            user_id=user_id,
            app_session_id=app_session_id,
            call_instance_id=call_instance_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LiveKit chưa được cấu hình sẵn sàng",
        ) from exc

    return LiveKitTokenResponseDTO(
        server_url=details.server_url,
        participant_token=details.participant_token,
    )


@router.post("/operator-token", response_model=LiveKitOperatorTokenResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_operator_livekit_token(
    request: LiveKitOperatorTokenRequestDTO,
    authorization: str | None = Header(default=None),
    token_service: LiveKitTokenService = Depends(get_livekit_token_service),
) -> LiveKitOperatorTokenResponseDTO:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    operator = await auth_service.get_user_for_token_durable(token)
    if operator is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập")
    if operator.get("role") not in {"OPERATOR", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ tổng đài viên được tham gia cuộc gọi")
    handoff = await handoff_service.get_handoff_durable(request.handoff_id)
    if handoff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy yêu cầu chuyển")
    if handoff.get("status") != "accepted" or handoff.get("operator_id") != operator.get("user_id"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handoff chưa được operator nhận")
    room_name = str(handoff.get("room_name") or "")
    if not room_name:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handoff chưa có LiveKit room")
    try:
        details = token_service.issue_for_operator(
            operator_id=str(operator["user_id"]),
            handoff_id=request.handoff_id,
            room_name=room_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LiveKit chưa sẵn sàng") from exc
    return LiveKitOperatorTokenResponseDTO(
        server_url=details.server_url,
        participant_token=details.participant_token,
        handoff_id=request.handoff_id,
        room_name=room_name,
    )
