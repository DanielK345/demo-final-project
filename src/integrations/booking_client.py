class BookingClient:
    async def create_booking(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "pending", "payload": payload}
