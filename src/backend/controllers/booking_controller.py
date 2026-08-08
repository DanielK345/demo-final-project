from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO
from src.backend.services.booking_service import BookingService


class BookingController:
    def __init__(self, service: BookingService | None = None) -> None:
        self.service = service or BookingService()

    async def create_booking(self, request: BookingRequestDTO) -> BookingResponseDTO:
        return BookingResponseDTO(**self.service.create_booking(request.model_dump()))
