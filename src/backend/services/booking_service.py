from datetime import UTC, datetime
from uuid import uuid4


class BookingService:
    bookings_by_key: dict[str, dict[str, object]] = {}
    # booking_id -> record (mọi booking, bất kể tạo qua đường nào) — phục vụ
    # GET /api/v1/bookings (lịch sử) và GET /api/v1/trips/status (tra cứu theo booking).
    bookings_by_id: dict[str, dict[str, object]] = {}
    _order: list[str] = []  # thứ tự tạo, để list theo mới nhất trước

    def create_booking(self, payload: dict[str, object]) -> dict[str, object]:
        key = str(payload.get("idempotency_key") or "")
        if key and key in self.bookings_by_key:
            return {**self.bookings_by_key[key], "status": "ALREADY_CREATED"}
        booking = {
            "booking_id": f"book_{uuid4().hex[:8]}",
            "status": "SEARCHING_DRIVER",
            "estimated_fare": int(payload.get("estimated_fare") or 85000),
            "currency": "VND",
            "eta_minutes": 5,
            "user_id": payload.get("user_id"),
            "pickup": payload.get("pickup"),
            "destination": payload.get("destination"),
            "vehicle_type": payload.get("vehicle_type"),
            "created_at": datetime.now(UTC).isoformat(),
        }
        if key:
            self.bookings_by_key[key] = booking
        self.bookings_by_id[booking["booking_id"]] = booking
        self._order.append(booking["booking_id"])
        return booking

    def create_booking_from_session(self, session: dict[str, object]) -> dict[str, object]:
        return self.create_booking({
            "idempotency_key": f"{session['session_id']}:create_booking:1",
            "estimated_fare": 85000,
            "user_id": session.get("user_id"),
            "pickup": session.get("pickup"),
            "destination": session.get("destination"),
            "vehicle_type": session.get("vehicle_type"),
        })

    def legacy_create_booking(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "booking_id": f"book_{uuid4().hex[:8]}",
            "status": "pending",
            "eta_minutes": None,
        }

    def get_booking(self, booking_id: str) -> dict[str, object] | None:
        return self.bookings_by_id.get(booking_id)

    def list_bookings_for_user(self, user_id: str) -> list[dict[str, object]]:
        """Mới nhất trước — dùng cho `GET /api/v1/bookings` (Activity/lịch sử chuyến)."""
        return [
            self.bookings_by_id[booking_id]
            for booking_id in reversed(self._order)
            if self.bookings_by_id[booking_id].get("user_id") == user_id
        ]
