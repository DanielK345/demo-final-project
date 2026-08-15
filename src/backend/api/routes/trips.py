from fastapi import APIRouter, HTTPException, Query, status

from src.backend.controllers.trip_controller import TripController
from src.backend.schemas.trip import TripStatusDTO

router = APIRouter(prefix="/trips", tags=["trips"])
controller = TripController()


@router.get("/status", response_model=TripStatusDTO)
async def get_trip_status(session_id: str = Query(..., min_length=1)) -> TripStatusDTO:
    try:
        return await controller.get_trip_status(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
