class TripClient:
    async def get_status(self, session_id: str) -> dict[str, object]:
        return {"session_id": session_id, "status": "driver_arriving", "eta_minutes": 5}
