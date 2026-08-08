from src.schemas.session import SessionDTO, SessionResumeResponseDTO, SessionUpdateDTO
from src.services.session_service import SessionService


class SessionController:
    def __init__(self, service: SessionService | None = None) -> None:
        self.service = service or SessionService()

    async def get_session(self, session_id: str) -> SessionDTO:
        return SessionDTO(**self.service.get_session(session_id))

    async def update_session(self, session_id: str, request: SessionUpdateDTO) -> SessionDTO:
        return SessionDTO(**self.service.update_session(session_id, request.model_dump(exclude_none=True)))

    async def resume_session(self, session_id: str) -> SessionResumeResponseDTO:
        return SessionResumeResponseDTO(**self.service.resume_session(session_id))
