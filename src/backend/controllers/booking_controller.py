from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO, BookingSummaryDTO
from src.backend.services.booking_service import BookingService


class BookingController:
    def __init__(self, service: BookingService | None = None) -> None:
        self.service = service or BookingService()

    async def create_booking(
        self, request: BookingRequestDTO, user_id: str, idempotency_key: str
    ) -> BookingResponseDTO:
        payload = request.model_dump(mode="json")
        payload.update({"idempotency_key": idempotency_key, "user_id": user_id})
        return BookingResponseDTO(**await self.service.create_booking_from_quote(payload))

    async def list_bookings(self, user_id: str) -> list[BookingSummaryDTO]:
        return [BookingSummaryDTO(**booking) for booking in await self.service.list_bookings_for_user_durable(user_id)]
