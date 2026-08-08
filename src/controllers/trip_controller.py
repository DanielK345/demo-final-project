from src.schemas.trip import TripStatusDTO
from src.services.trip_service import TripService


class TripController:
    def __init__(self, service: TripService | None = None) -> None:
        self.service = service or TripService()

    async def get_trip_status(self, session_id: str) -> TripStatusDTO:
        return TripStatusDTO(**self.service.get_status(session_id))
