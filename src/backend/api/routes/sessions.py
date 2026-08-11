from fastapi import APIRouter, Header, HTTPException, status

from src.backend.controllers.session_controller import SessionController
from src.backend.api.routes.auth import service as auth_service
from src.backend.schemas.session import (
    CreateSessionDTO,
    EndSessionDTO,
    EndSessionResponseDTO,
    SessionCreatedDTO,
    SessionDTO,
    SessionMessageDTO,
    SessionMessageResponseDTO,
    SessionResumeResponseDTO,
    SessionUpdateDTO,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()


def _user_id_from_header(authorization: str | None) -> str:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    user = auth_service.get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập để bắt đầu hội thoại")
    return user["user_id"]


@router.post("", response_model=SessionCreatedDTO, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionDTO, authorization: str | None = Header(default=None)) -> SessionCreatedDTO:
    return SessionCreatedDTO(**controller.service.create_session(_user_id_from_header(authorization), request.channel, request.device_id))


@router.get("/{session_id}", response_model=SessionDTO)
async def get_session(session_id: str) -> SessionDTO:
    try:
        return await controller.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{session_id}", response_model=SessionDTO)
async def update_session(session_id: str, request: SessionUpdateDTO) -> SessionDTO:
    try:
        return await controller.update_session(session_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/resume", response_model=SessionResumeResponseDTO)
async def resume_session(session_id: str) -> SessionResumeResponseDTO:
    try:
        return await controller.resume_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/messages", response_model=SessionMessageResponseDTO)
async def send_message(session_id: str, request: SessionMessageDTO) -> SessionMessageResponseDTO:
    try:
        return SessionMessageResponseDTO(**controller.service.process_message(session_id, request.message, request.stt_confidence))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/end", response_model=EndSessionResponseDTO)
async def end_session(session_id: str, request: EndSessionDTO) -> EndSessionResponseDTO:
    try:
        return EndSessionResponseDTO(**controller.service.end_session(session_id, request.reason))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
