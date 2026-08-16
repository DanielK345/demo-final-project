import hashlib
from datetime import UTC, datetime

from src.backend.config import get_settings
from src.backend.repositories.persistence_repository import PersistenceRepository

# Mô phỏng tài xế/xe — KHÔNG phải dữ liệu thật (không có hệ thống điều phối tài xế
# thật), nhưng ổn định theo booking_id (seed từ hash) thay vì random mỗi lần gọi như
# code cũ — sửa đúng bug đã ghi trong mustdo.md mục "Database thật".
_DRIVER_NAMES = ["Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Nam", "Phạm Thị Hương", "Đỗ Văn Long"]
_VEHICLE_MODELS = ["VinFast VF8", "VinFast VF9", "Hyundai Kona Electric", "Kia EV6"]

# Mốc thời gian mô phỏng tiến trình chuyến đi (giây kể từ lúc tạo trip).
_STAGES: list[tuple[float, str, int]] = [
    (8, "SEARCHING_DRIVER", 8),
    (20, "DRIVER_ASSIGNED", 5),
    (40, "ARRIVING", 2),
    (70, "ON_TRIP", 0),
]
_FINAL_STAGE = ("COMPLETED", 0)


class TripService:
    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()

    async def get_status_for_booking_durable(self, booking_id: str) -> dict[str, object]:
        if get_settings().app_env == "test":
            return self.get_status_for_booking(booking_id)
        defaults = self._create_trip(booking_id)
        defaults.pop("trip_id", None)
        defaults.pop("booking_id", None)
        created_at = defaults.pop("created_at")
        trip = await self._repository.get_or_create_trip(booking_id, defaults)
        row_created = trip.get("created_at") or created_at
        if isinstance(row_created, str):
            row_created = datetime.fromisoformat(row_created)
        assert isinstance(row_created, datetime)
        elapsed = (datetime.now(UTC) - row_created).total_seconds()
        status, eta = _FINAL_STAGE
        for threshold, candidate_status, candidate_eta in _STAGES:
            if elapsed < threshold:
                status, eta = candidate_status, candidate_eta
                break
        await self._repository.update_trip(booking_id, status=status, eta_minutes=eta)
        trip["status"], trip["eta_minutes"] = status, eta
        return trip
    trips_by_booking: dict[str, dict[str, object]] = {}

    def get_status_for_booking(self, booking_id: str) -> dict[str, object]:
        trip = self.trips_by_booking.get(booking_id)
        if trip is None:
            trip = self._create_trip(booking_id)
            self.trips_by_booking[booking_id] = trip
        self._advance(trip)
        return trip

    @staticmethod
    def _create_trip(booking_id: str) -> dict[str, object]:
        seed = int(hashlib.sha256(booking_id.encode("utf-8")).hexdigest(), 16)
        driver_name = _DRIVER_NAMES[seed % len(_DRIVER_NAMES)]
        vehicle = _VEHICLE_MODELS[(seed // len(_DRIVER_NAMES)) % len(_VEHICLE_MODELS)]
        plate = f"51K-{(seed % 900) + 100}.{(seed // 900) % 100:02d}"
        return {
            "trip_id": f"trip_{booking_id.removeprefix('book_')}",
            "booking_id": booking_id,
            "status": "SEARCHING_DRIVER",
            "eta_minutes": 8,
            "driver_name": driver_name,
            "vehicle": vehicle,
            "license_plate": plate,
            "driver_rating": round(4.6 + (seed % 40) / 100, 1),
            "driver_phone": f"09{(seed % 90000000) + 10000000:08d}",
            "created_at": datetime.now(UTC),
        }

    @staticmethod
    def _advance(trip: dict[str, object]) -> None:
        created_at = trip["created_at"]
        assert isinstance(created_at, datetime)
        elapsed = (datetime.now(UTC) - created_at).total_seconds()
        for threshold, status, eta in _STAGES:
            if elapsed < threshold:
                trip["status"], trip["eta_minutes"] = status, eta
                return
        trip["status"], trip["eta_minutes"] = _FINAL_STAGE
