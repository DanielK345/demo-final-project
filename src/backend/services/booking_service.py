from uuid import uuid4


class BookingService:
    def create_booking(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "booking_id": f"book_{uuid4().hex[:8]}",
            "status": "pending",
            "eta_minutes": None,
        }
