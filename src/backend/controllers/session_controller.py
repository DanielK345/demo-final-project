from src.backend.schemas.session import SessionDTO, SessionResumeResponseDTO, SessionUpdateDTO
from src.backend.services.session_service import SessionService


class SessionController:
    def __init__(self, service: SessionService | None = None) -> None:
        self.service = service or SessionService()

    async def get_session(self, session_id: str) -> SessionDTO:
        return SessionDTO(**await self.service.get_session_durable(session_id))

    async def update_session(self, session_id: str, request: SessionUpdateDTO) -> SessionDTO:
        return SessionDTO(
            **await self.service.update_session_durable(session_id, request.model_dump(exclude_none=True))
        )

    async def resume_session(self, session_id: str) -> SessionResumeResponseDTO:
        return SessionResumeResponseDTO(**await self.service.resume_session_durable(session_id))
