from fastapi import APIRouter, Header, HTTPException, status

from src.backend.api.routes.auth import service as auth_service
from src.backend.controllers.session_controller import SessionController
from src.backend.schemas.session import (
    CreateSessionDTO,
    EndSessionDTO,
    EndSessionResponseDTO,
    SessionCreatedDTO,
    SessionDTO,
    SessionFeedbackDTO,
    SessionFeedbackResponseDTO,
    SessionHistorySummaryDTO,
    SessionMessageDTO,
    SessionMessageResponseDTO,
    SessionResetResponseDTO,
    SessionResumeResponseDTO,
    SessionTranscriptDTO,
    SessionUpdateDTO,
)
from src.backend.services.conversation_history_service import ConversationHistoryService

router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()
_history_service = ConversationHistoryService()
_SESSION_AUTH_MESSAGE = "Phiên hội thoại không hợp lệ. Vui lòng đăng nhập lại."
_SESSION_CHANGED_MESSAGE = "Phiên hội thoại đã thay đổi. Vui lòng dùng phiên hiện tại hoặc bắt đầu phiên mới."


def _token_from_header(authorization: str | None) -> str:
    return authorization.removeprefix("Bearer ") if authorization else ""


async def _user_from_header(authorization: str | None) -> dict[str, object]:
    token = _token_from_header(authorization)
    user = await auth_service.get_user_for_token_durable(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để bắt đầu hội thoại",
        )
    return user


async def _user_id_from_header(authorization: str | None) -> str:
    return str((await _user_from_header(authorization))["user_id"])


async def _require_session_access(session_id: str, authorization: str | None) -> str:
    token = _token_from_header(authorization)
    user = await auth_service.get_user_for_token_durable(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        )

    bound_session_id = await auth_service.get_session_for_token_durable(token)
    if not bound_session_id or bound_session_id != session_id:
        raise HTTPException(
            # Token vẫn hợp lệ; chỉ có session mà client đang giữ đã cũ. Trả 401 ở
            # đây khiến frontend hiểu nhầm là hết đăng nhập và xóa luôn token.
            status_code=status.HTTP_409_CONFLICT,
            detail=_SESSION_CHANGED_MESSAGE,
        )

    session = await controller.service.get_session_durable(session_id)
    if session is None or session.get("user_id") != user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_SESSION_CHANGED_MESSAGE,
        )
    return user["user_id"]


@router.post("", response_model=SessionCreatedDTO, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionDTO,
    authorization: str | None = Header(default=None),
) -> SessionCreatedDTO:
    user = await _user_from_header(authorization)
    created = await controller.service.create_session_durable(
        user["user_id"], request.channel, request.device_id, phone=user.get("phone")
    )
    token = _token_from_header(authorization)
    if token:
        await auth_service.bind_session_to_token_durable(token, str(created["session_id"]))
    return SessionCreatedDTO(**created)


@router.get("/history", response_model=list[SessionHistorySummaryDTO])
async def list_session_history(authorization: str | None = Header(default=None)) -> list[SessionHistorySummaryDTO]:
    """Lịch sử toàn bộ cuộc trò chuyện của user hiện tại — không dùng
    `_require_session_access` (token chỉ bind với ĐÚNG 1 session đang hoạt động,
    không phải các session cũ), chỉ cần xác thực user qua token là đủ để xem lịch sử
    của chính mình."""
    user_id = await _user_id_from_header(authorization)
    return [SessionHistorySummaryDTO(**item) for item in await _history_service.list_sessions_durable(user_id)]


@router.get("/history/{session_id}", response_model=SessionTranscriptDTO)
async def get_session_transcript(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> SessionTranscriptDTO:
    user_id = await _user_id_from_header(authorization)
    transcript = await _history_service.get_transcript_durable(user_id, session_id)
    if transcript is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lịch sử hội thoại")
    return SessionTranscriptDTO(**transcript)


@router.get("/{session_id}", response_model=SessionDTO)
async def get_session(session_id: str, authorization: str | None = Header(default=None)) -> SessionDTO:
    await _require_session_access(session_id, authorization)
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
    await _require_session_access(session_id, authorization)
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
    await _require_session_access(session_id, authorization)
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
    await _require_session_access(session_id, authorization)
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
    await _require_session_access(session_id, authorization)
    try:
        return SessionFeedbackResponseDTO(
            **await controller.service.submit_feedback_durable(
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
    await _require_session_access(session_id, authorization)
    try:
        return EndSessionResponseDTO(**await controller.service.end_session_durable(session_id, request.reason))
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_SESSION_AUTH_MESSAGE,
        ) from exc


@router.post("/{session_id}/reset", response_model=SessionResetResponseDTO)
async def reset_conversation(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> SessionResetResponseDTO:
    await _require_session_access(session_id, authorization)
    try:
        return SessionResetResponseDTO(**await controller.service.reset_conversation_durable(session_id))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_AUTH_MESSAGE) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
