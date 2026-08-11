from uuid import uuid4


class BookingService:
    bookings_by_key: dict[str, dict[str, object]] = {}

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
        }
        if key:
            self.bookings_by_key[key] = booking
        return booking

    def create_booking_from_session(self, session: dict[str, object]) -> dict[str, object]:
        return self.create_booking({
            "idempotency_key": f"{session['session_id']}:create_booking:1",
            "estimated_fare": 85000,
        })

    def legacy_create_booking(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "booking_id": f"book_{uuid4().hex[:8]}",
            "status": "pending",
            "eta_minutes": None,
        }
