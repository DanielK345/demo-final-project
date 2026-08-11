from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO
from src.backend.services.booking_service import BookingService
from src.backend.services.session_service import SessionService


class BookingController:
    def __init__(self, service: BookingService | None = None) -> None:
        self.service = service or BookingService()

    async def create_booking(self, request: BookingRequestDTO, idempotency_key: str | None = None) -> BookingResponseDTO:
        if not request.fare_confirmed:
            raise ValueError("Cần xác nhận giá trước khi đặt xe")
        session = SessionService.sessions.get(request.session_id)
        if session is None or session.get("confirmation_status") != "confirmed":
            raise ValueError("Phiên đặt xe chưa nhận được xác nhận rõ ràng từ khách hàng")
        payload = request.model_dump()
        payload["idempotency_key"] = idempotency_key
        return BookingResponseDTO(**self.service.create_booking(payload))
