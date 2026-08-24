from src.backend.schemas.handoff import HandoffAcceptanceDTO, HandoffDTO, HandoffResponseDTO
from src.backend.services.handoff_service import HandoffService


class HandoffController:
    def __init__(self, service: HandoffService | None = None) -> None:
        self.service = service or HandoffService()

    async def create_handoff(self, request: HandoffDTO) -> HandoffResponseDTO:
        return HandoffResponseDTO(**await self.service.create_handoff_durable(request.model_dump()))

    async def list_handoffs(self, status: str) -> list[HandoffResponseDTO]:
        return [HandoffResponseDTO(**item) for item in await self.service.list_handoffs_durable(status)]

    async def accept_handoff(self, handoff_id: str, operator_id: str | None = None) -> HandoffAcceptanceDTO:
        return HandoffAcceptanceDTO(**await self.service.accept_handoff_durable(handoff_id, operator_id))

    async def get_handoff(self, handoff_id: str) -> HandoffResponseDTO | None:
        record = await self.service.get_handoff_durable(handoff_id)
        return HandoffResponseDTO(**record) if record is not None else None

    async def resolve_handoff(self, handoff_id: str, operator_id: str) -> HandoffResponseDTO:
        return HandoffResponseDTO(**await self.service.resolve_handoff_durable(handoff_id, operator_id))

    async def connect_handoff(self, handoff_id: str, operator_id: str) -> HandoffResponseDTO:
        return HandoffResponseDTO(**await self.service.connect_handoff_durable(handoff_id, operator_id))
