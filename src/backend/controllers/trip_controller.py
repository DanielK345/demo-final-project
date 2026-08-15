from src.backend.schemas.trip import TripStatusDTO
from src.backend.services.session_service import SessionService
from src.backend.services.trip_service import TripService


class TripController:
    def __init__(self, service: TripService | None = None) -> None:
        self.service = service or TripService()

    async def get_trip_status(self, session_id: str) -> TripStatusDTO:
        session = SessionService.sessions.get(session_id)
        if session is None:
            raise KeyError("Không tìm thấy phiên hội thoại")
        booking_id = session.get("booking_id")
        if not booking_id:
            raise ValueError("Phiên này chưa có chuyến đi nào được đặt")
        return TripStatusDTO(**self.service.get_status_for_booking(str(booking_id)))
