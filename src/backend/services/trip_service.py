from uuid import uuid4


class TripService:
    def get_status(self, session_id: str) -> dict[str, object]:
        return {
            "trip_id": f"trip_{uuid4().hex[:8]}",
            "status": "driver_arriving",
            "eta_minutes": 5,
        }
