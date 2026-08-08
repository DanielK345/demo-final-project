from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class BookingRecord:
    id: str
    call_id: str
    external_booking_id: str | None
    vehicle_type: str
    status: str
    created_at: datetime
