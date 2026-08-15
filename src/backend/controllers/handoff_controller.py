from src.backend.schemas.handoff import HandoffAcceptanceDTO, HandoffDTO, HandoffResponseDTO
from src.backend.services.handoff_service import HandoffService


class HandoffController:
    def __init__(self, service: HandoffService | None = None) -> None:
        self.service = service or HandoffService()

    async def create_handoff(self, request: HandoffDTO) -> HandoffResponseDTO:
        return HandoffResponseDTO(**self.service.create_handoff(request.model_dump()))

    async def list_handoffs(self, status: str) -> list[HandoffResponseDTO]:
        return [HandoffResponseDTO(**item) for item in self.service.list_handoffs(status)]

    async def accept_handoff(self, handoff_id: str) -> HandoffAcceptanceDTO:
        return HandoffAcceptanceDTO(**self.service.accept_handoff(handoff_id))
