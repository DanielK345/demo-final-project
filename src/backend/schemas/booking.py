from pydantic import BaseModel

from src.backend.schemas.common import LocationDTO


class BookingRequestDTO(BaseModel):
    session_id: str
    pickup: LocationDTO
    destination: LocationDTO
    vehicle_type: str
    fare_confirmed: bool = False
    estimated_fare: int | None = None


class BookingResponseDTO(BaseModel):
    booking_id: str
    status: str
    eta_minutes: int | None = None
    estimated_fare: int | None = None
    currency: str = "VND"


class BookingSummaryDTO(BaseModel):
    """1 dòng trong lịch sử đặt xe — `GET /api/v1/bookings`.

    `pickup`/`destination` cố ý để `dict` lỏng (không ép `LocationDTO`) — booking tạo
    qua Core Agent (chat/voice) lưu địa điểm dạng `{place_id, display_name, address}`
    (xem `AgentToolExecutor._dispatch`), khác field với `LocationDTO`
    (`name/lat/lng/place_id`) mà `POST /bookings` (form-based, `BookingPage`) dùng.
    2 nguồn khác field thật — hợp nhất lại là việc lớn hơn, ngoài phạm vi ở đây; ép
    kiểu ở DTO hiển thị (chỉ cần show text) là đủ và không rủi ro."""

    booking_id: str
    status: str
    estimated_fare: int | None = None
    currency: str = "VND"
    pickup: dict[str, object] | None = None
    destination: dict[str, object] | None = None
    vehicle_type: str | None = None
    created_at: str | None = None
