from src.backend.schemas.call import CallResponseDTO, CreateCallDTO
from src.backend.services.call_service import CallService


class CallController:
    def __init__(self, service: CallService | None = None) -> None:
        self.service = service or CallService()

    async def start_call(self, request: CreateCallDTO) -> CallResponseDTO:
        payload = self.service.create_call(request.customer_phone)
        return CallResponseDTO(**payload)
