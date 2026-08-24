from fastapi import APIRouter, Header, HTTPException, status

from src.backend.api.routes.sessions import _require_session_access, _user_id_from_header
from src.backend.controllers.booking_controller import BookingController
from src.backend.schemas.booking import BookingRequestDTO, BookingResponseDTO, BookingSummaryDTO

router = APIRouter(prefix="/bookings", tags=["bookings"])
controller = BookingController()


@router.post("", response_model=BookingResponseDTO)
async def create_booking(
    request: BookingRequestDTO,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
) -> BookingResponseDTO:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu Idempotency-Key")
    try:
        user_id = await _require_session_access(request.session_id, authorization)
        return await controller.create_booking(request, user_id, idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[BookingSummaryDTO])
async def list_bookings(authorization: str | None = Header(default=None)) -> list[BookingSummaryDTO]:
    """Lịch sử đặt xe của người dùng hiện tại — dùng bởi `ActivityPage`/`HomePage`
    (Frontend). Trả cả booking tạo qua chat/voice (Core Agent) lẫn qua form
    (`BookingPage`) vì cả 2 đường đều cuối cùng gọi `BookingService.create_booking`."""
    user_id = await _user_id_from_header(authorization)
    return await controller.list_bookings(user_id)
