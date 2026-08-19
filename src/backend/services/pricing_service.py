from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from src.backend.services.pricing_catalog import PricingCatalog, VehiclePricing, load_pricing_catalog

_AVG_SPEED_KMH = 24.0
_QUOTE_TTL_SECONDS = 300


def _route_seed(pickup_place_id: str, destination_place_id: str) -> int:
    return int(hashlib.sha256(f"{pickup_place_id}:{destination_place_id}".encode()).hexdigest(), 16)


def estimate_distance_km(pickup_place_id: str, destination_place_id: str) -> float:
    """Deterministic compatibility helper; production quote paths must not call it."""
    return round(1.2 + (_route_seed(pickup_place_id, destination_place_id) % 1680) / 100, 1)


def _eta_minutes(distance_km: float, duration_seconds: float | None = None) -> int:
    return (
        max(1, round(duration_seconds / 60))
        if duration_seconds is not None
        else max(1, round(distance_km / _AVG_SPEED_KMH * 60))
    )


def calculate_distance_fare(distance_km: float, pricing: VehiclePricing) -> int:
    total = float(pricing.base_fare)
    cursor = pricing.base_km
    route_end = max(distance_km, pricing.base_km)
    for tier in pricing.tiers:
        end = route_end if tier.up_to_km is None else min(route_end, tier.up_to_km)
        if end > cursor:
            total += (end - cursor) * tier.per_km
            cursor = end
        if cursor >= route_end:
            break
    return max(pricing.min_fare, round(total))


class PricingService:
    """Versioned pricing; production calculations require provider route measurements."""

    def __init__(self, catalog: PricingCatalog | None = None) -> None:
        self.catalog = catalog or load_pricing_catalog()

    def _estimate_id(self, route_id: str, vehicle_type: str) -> str:
        source = f"{self.catalog.version}:{self.catalog.region}:{route_id}:{vehicle_type}"
        return f"est_{hashlib.sha256(source.encode()).hexdigest()[:12]}"

    def estimate_route_fare(
        self, *, route_id: str, distance_meters: float, duration_seconds: float, vehicle_type: str
    ) -> dict[str, object]:
        if distance_meters < 0 or duration_seconds < 0:
            raise ValueError("INVALID_ROUTE_MEASUREMENTS")
        pricing = self.catalog.vehicles.get(vehicle_type)
        if pricing is None:
            raise ValueError(f"Unknown vehicle type: {vehicle_type}")
        distance_km = round(distance_meters / 1000, 3)
        fare = calculate_distance_fare(distance_km, pricing)
        now = datetime.now(UTC)
        return {
            "estimate_id": self._estimate_id(route_id, vehicle_type),
            "pricing_version": self.catalog.version,
            "pricing_region": self.catalog.region,
            "pricing_status": self.catalog.status,
            "fare_amount": fare,
            "currency": self.catalog.currency,
            "eta_minutes": _eta_minutes(distance_km, duration_seconds),
            "distance_km": distance_km,
            "fare_breakdown": {
                "base_fare": pricing.base_fare,
                "base_km": pricing.base_km,
                "distance_fare": fare - pricing.base_fare,
                "time_fare": 0,
                "surcharge_amount": 0,
                "applied_surcharges": [],
            },
            "rate_metadata": {
                "per_minute": pricing.per_minute,
                "surcharges": pricing.surcharges,
                "source_ref": pricing.source_ref,
            },
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=_QUOTE_TTL_SECONDS)).isoformat(),
            "estimated": True,
            "data_quality": self.catalog.data_quality,
            "source_type": self.catalog.source_type,
        }

    def estimate_fare(self, *, pickup_place_id: str, destination_place_id: str, vehicle_type: str) -> dict[str, object]:
        """Legacy deterministic estimator retained only for test/offline compatibility."""
        distance_km = estimate_distance_km(pickup_place_id, destination_place_id)
        return self.estimate_route_fare(
            route_id=f"demo_{pickup_place_id}_{destination_place_id}",
            distance_meters=distance_km * 1000,
            duration_seconds=_eta_minutes(distance_km) * 60,
            vehicle_type=vehicle_type,
        )

    def vehicle_options_for_route(
        self,
        *,
        route_id: str,
        distance_meters: float,
        duration_seconds: float,
        passenger_count: int,
        luggage_count: int | None = None,
    ) -> list[dict[str, object]]:
        options: list[dict[str, object]] = []
        for vehicle_type, vehicle in self.catalog.vehicles.items():
            quote = self.estimate_route_fare(
                route_id=route_id,
                distance_meters=distance_meters,
                duration_seconds=duration_seconds,
                vehicle_type=vehicle_type,
            )
            options.append(
                {
                    "option_id": f"opt_{vehicle_type.lower()}",
                    "vehicle_type": vehicle_type,
                    "display_name": vehicle.display_name,
                    "capacity": vehicle.capacity,
                    "luggage_capacity": vehicle.luggage_capacity,
                    "available": passenger_count <= vehicle.capacity
                    and (luggage_count is None or luggage_count <= vehicle.luggage_capacity),
                    **quote,
                }
            )
        return options

    def vehicle_options(
        self, *, pickup_place_id: str, destination_place_id: str, passenger_count: int, luggage_count: int | None = None
    ) -> list[dict[str, object]]:
        distance_km = estimate_distance_km(pickup_place_id, destination_place_id)
        return self.vehicle_options_for_route(
            route_id=f"demo_{pickup_place_id}_{destination_place_id}",
            distance_meters=distance_km * 1000,
            duration_seconds=_eta_minutes(distance_km) * 60,
            passenger_count=passenger_count,
            luggage_count=luggage_count,
        )

    def cancellation_policy(self) -> dict[str, object]:
        return self.catalog.cancellation_policy.model_dump(mode="json")
