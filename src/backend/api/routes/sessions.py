from fastapi import APIRouter, Header, HTTPException, status

from src.backend.controllers.session_controller import SessionController
from src.backend.api.routes.auth import service as auth_service
from src.backend.schemas.session import (
    CreateSessionDTO,
    EndSessionDTO,
    EndSessionResponseDTO,
    SessionCreatedDTO,
    SessionDTO,
    SessionFeedbackDTO,
    SessionFeedbackResponseDTO,
    SessionMessageDTO,
    SessionMessageResponseDTO,
    SessionResumeResponseDTO,
    SessionUpdateDTO,
)
from src.backend.services.session_service import SessionService


router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()
_SESSION_AUTH_MESSAGE = "Phiên hội thoại không hợp lệ. Vui lòng đăng nhập lại."


def _token_from_header(authorization: str | None) -> str:
    return authorization.removeprefix("Bearer ") if authorization else ""


def _user_id_from_header(authorization: str | None) -> str:
    token = _token_from_header(authorization)
    user = auth_service.get_user_for_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để bắt đầu hội thoại",
        )
    return user["user_id"]


def _require_session_access(session_id: str, authorization: str | None) -> str:
    token = _token_from_header(authorization)
    user = auth_service.get_user_for_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        )

    bound_session_id = auth_service.get_session_for_token(token)
    if not bound_session_id or bound_session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        )

    session = SessionService.sessions.get(session_id)
    if session is None or session.get("user_id") != user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        )
    return user["user_id"]


@router.post("", response_model=SessionCreatedDTO, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionDTO,
    authorization: str | None = Header(default=None),
) -> SessionCreatedDTO:
    user_id = _user_id_from_header(authorization)
    created = controller.service.create_session(user_id, request.channel, request.device_id)
    token = _token_from_header(authorization)
    if token:
        auth_service.bind_session_to_token(token, str(created["session_id"]))
    return SessionCreatedDTO(**created)


@router.get("/{session_id}", response_model=SessionDTO)
async def get_session(session_id: str, authorization: str | None = Header(default=None)) -> SessionDTO:
    _require_session_access(session_id, authorization)
    try:
        return await controller.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc


@router.patch("/{session_id}", response_model=SessionDTO)
async def update_session(
    session_id: str,
    request: SessionUpdateDTO,
    authorization: str | None = Header(default=None),
) -> SessionDTO:
    _require_session_access(session_id, authorization)
    try:
        return await controller.update_session(session_id, request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc


@router.post("/{session_id}/resume", response_model=SessionResumeResponseDTO)
async def resume_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> SessionResumeResponseDTO:
    _require_session_access(session_id, authorization)
    try:
        return await controller.resume_session(session_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc


@router.post("/{session_id}/messages", response_model=SessionMessageResponseDTO)
async def send_message(
    session_id: str,
    request: SessionMessageDTO,
    authorization: str | None = Header(default=None),
) -> SessionMessageResponseDTO:
    _require_session_access(session_id, authorization)
    try:
        return SessionMessageResponseDTO(
            **await controller.service.process_message(
                session_id,
                request.message,
                request.stt_confidence,
                source=request.source,
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/feedback", response_model=SessionFeedbackResponseDTO)
async def submit_feedback(
    session_id: str,
    request: SessionFeedbackDTO,
    authorization: str | None = Header(default=None),
) -> SessionFeedbackResponseDTO:
    _require_session_access(session_id, authorization)
    try:
        return SessionFeedbackResponseDTO(
            **controller.service.submit_feedback(
                session_id,
                request.rating,
                request.comment,
            )
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/end", response_model=EndSessionResponseDTO)
async def end_session(
    session_id: str,
    request: EndSessionDTO,
    authorization: str | None = Header(default=None),
) -> EndSessionResponseDTO:
    _require_session_access(session_id, authorization)
    try:
        return EndSessionResponseDTO(**controller.service.end_session(session_id, request.reason))
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc
