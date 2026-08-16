from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

# Chưa tích hợp Maps/routing API thật (xem mustdo.md mục Payment/Maps — cần
# credential thật). Khoảng cách/giá cước suy ra DETERMINISTIC theo đúng 1 cặp
# pickup/destination place_id (hash ổn định, không random mỗi lần gọi) — cùng
# nguyên tắc mô phỏng đã dùng ở TripService (driver/ETA theo hash booking_id). Không
# phải số liệu GPS thật, nhưng nhất quán giữa các lượt gọi và không giả vờ chính xác
# hơn thực tế đang có.

_FARE_PER_KM_VND: dict[str, int] = {
    "MOTORBIKE": 4000,
    "CAR_4": 11000,
    "CAR_7": 14000,
}
_VEHICLE_CATALOG: list[dict[str, object]] = [
    {"vehicle_type": "MOTORBIKE", "display_name": "Xe máy", "capacity": 1, "luggage_capacity": 0},
    {"vehicle_type": "CAR_4", "display_name": "Ô tô 4 chỗ", "capacity": 4, "luggage_capacity": 2},
    {"vehicle_type": "CAR_7", "display_name": "Ô tô 7 chỗ", "capacity": 7, "luggage_capacity": 4},
]
_BASE_OPEN_FARE_VND = 12000
_AVG_SPEED_KMH = 24.0
_PRICING_VERSION = "demo-2026-08-16"
_QUOTE_TTL_SECONDS = 300


def _route_seed(pickup_place_id: str, destination_place_id: str) -> int:
    digest = hashlib.sha256(f"{pickup_place_id}:{destination_place_id}".encode()).hexdigest()
    return int(digest, 16)


def estimate_distance_km(pickup_place_id: str, destination_place_id: str) -> float:
    seed = _route_seed(pickup_place_id, destination_place_id)
    # Biên 1.2 - 18.0 km — hợp lý cho di chuyển nội thành, ổn định theo đúng cặp điểm.
    return round(1.2 + (seed % 1680) / 100, 1)


def _eta_minutes(distance_km: float) -> int:
    return max(1, round(distance_km / _AVG_SPEED_KMH * 60))


def _estimate_id(pickup_place_id: str, destination_place_id: str, vehicle_type: str) -> str:
    digest = hashlib.sha256(f"{_PRICING_VERSION}:{pickup_place_id}:{destination_place_id}:{vehicle_type}".encode()).hexdigest()
    return f"est_{digest[:12]}"


class PricingService:
    """get_vehicle_options / estimate_fare thật — có danh mục xe cố định (xe máy/4
    chỗ/7 chỗ, đúng VehicleType của Core Agent) và công thức giá theo km rõ ràng, thay
    vì bịa 1 con số cố định (85.000đ) cho mọi chuyến như bản cũ."""

    def vehicle_options(
        self,
        *,
        pickup_place_id: str,
        destination_place_id: str,
        passenger_count: int,
        luggage_count: int | None = None,
    ) -> list[dict[str, object]]:
        distance_km = estimate_distance_km(pickup_place_id, destination_place_id)
        eta_minutes = _eta_minutes(distance_km)
        options: list[dict[str, object]] = []
        for vehicle in _VEHICLE_CATALOG:
            vehicle_type = str(vehicle["vehicle_type"])
            available = passenger_count <= int(vehicle["capacity"]) and (
                luggage_count is None or luggage_count <= int(vehicle["luggage_capacity"])
            )
            fare = round(_BASE_OPEN_FARE_VND + distance_km * _FARE_PER_KM_VND[vehicle_type])
            options.append(
                {
                    "option_id": f"opt_{vehicle_type.lower()}",
                    "vehicle_type": vehicle_type,
                    "display_name": vehicle["display_name"],
                    "capacity": vehicle["capacity"],
                    "luggage_capacity": vehicle["luggage_capacity"],
                    "available": available,
                    "estimate_id": _estimate_id(pickup_place_id, destination_place_id, vehicle_type),
                    "fare_amount": fare,
                    "currency": "VND",
                    "eta_minutes": eta_minutes,
                }
            )
        return options

    def estimate_fare(
        self,
        *,
        pickup_place_id: str,
        destination_place_id: str,
        vehicle_type: str,
    ) -> dict[str, object]:
        distance_km = estimate_distance_km(pickup_place_id, destination_place_id)
        if vehicle_type not in _FARE_PER_KM_VND:
            raise ValueError(f"Unknown vehicle type: {vehicle_type}")
        per_km = _FARE_PER_KM_VND[vehicle_type]
        fare = round(_BASE_OPEN_FARE_VND + distance_km * per_km)
        now = datetime.now(UTC)
        return {
            "estimate_id": _estimate_id(pickup_place_id, destination_place_id, vehicle_type),
            "pricing_version": _PRICING_VERSION,
            "fare_amount": fare,
            "currency": "VND",
            "eta_minutes": _eta_minutes(distance_km),
            "distance_km": distance_km,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=_QUOTE_TTL_SECONDS)).isoformat(),
            "estimated": True,
            "data_quality": "DEMO",
        }
