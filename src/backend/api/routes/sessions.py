from fastapi import APIRouter

from src.backend.controllers.session_controller import SessionController
from src.backend.schemas.session import SessionDTO, SessionResumeResponseDTO, SessionUpdateDTO


router = APIRouter(prefix="/sessions", tags=["sessions"])
controller = SessionController()


@router.get("/{session_id}", response_model=SessionDTO)
async def get_session(session_id: str) -> SessionDTO:
    return await controller.get_session(session_id)


@router.patch("/{session_id}", response_model=SessionDTO)
async def update_session(session_id: str, request: SessionUpdateDTO) -> SessionDTO:
    return await controller.update_session(session_id, request)


@router.post("/{session_id}/resume", response_model=SessionResumeResponseDTO)
async def resume_session(session_id: str) -> SessionResumeResponseDTO:
    return await controller.resume_session(session_id)
