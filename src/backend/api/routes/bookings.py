from fastapi import APIRouter

from src.backend.controllers.booking_controller import BookingController
from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO


router = APIRouter(prefix="/bookings", tags=["bookings"])
controller = BookingController()


@router.post("", response_model=BookingResponseDTO)
async def create_booking(request: BookingRequestDTO) -> BookingResponseDTO:
    return await controller.create_booking(request)
