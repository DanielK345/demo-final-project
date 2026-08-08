from fastapi import APIRouter, Query

from src.backend.controllers.trip_controller import TripController
from src.backend.schemas.trip import TripStatusDTO


router = APIRouter(prefix="/trips", tags=["trips"])
controller = TripController()


@router.get("/status", response_model=TripStatusDTO)
async def get_trip_status(session_id: str = Query(..., min_length=1)) -> TripStatusDTO:
    return await controller.get_trip_status(session_id)
