from fastapi import APIRouter, Header, HTTPException, status

from src.backend.controllers.booking_controller import BookingController
from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO


router = APIRouter(prefix="/bookings", tags=["bookings"])
controller = BookingController()


@router.post("", response_model=BookingResponseDTO)
async def create_booking(request: BookingRequestDTO, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> BookingResponseDTO:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu Idempotency-Key")
    try:
        return await controller.create_booking(request, idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
