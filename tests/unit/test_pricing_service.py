"""Unit test cho PricingService và Vehicle Catalog của AloSM Voice AI."""

from __future__ import annotations

from src.backend.services.pricing_service import PricingService, estimate_distance_km


def test_estimate_distance_deterministic():
    d1 = estimate_distance_km("place_tsn", "place_vincom")
    d2 = estimate_distance_km("place_tsn", "place_vincom")
    assert d1 == d2
    assert d1 > 0


def test_vehicle_options_catalog():
    service = PricingService()
    options = service.vehicle_options(
        pickup_place_id="place_a",
        destination_place_id="place_b",
        passenger_count=2,
        luggage_count=1,
    )
    assert len(options) == 4  # MOTORBIKE, CAR_4, CAR_7, LUXURY
    vehicle_types = [opt["vehicle_type"] for opt in options]
    assert "MOTORBIKE" in vehicle_types
    assert "CAR_4" in vehicle_types
    assert "CAR_7" in vehicle_types
    assert "LUXURY" in vehicle_types


def test_vehicle_capacity_filtering():
    service = PricingService()
    options = service.vehicle_options(
        pickup_place_id="place_a",
        destination_place_id="place_b",
        passenger_count=5,  # 5 khách -> Xe máy & 4 chỗ không đủ chỗ
        luggage_count=2,
    )
    by_type = {opt["vehicle_type"]: opt["available"] for opt in options}
    assert by_type["MOTORBIKE"] is False
    assert by_type["CAR_4"] is False
    assert by_type["CAR_7"] is True


def test_estimate_fare_calculation():
    service = PricingService()
    res = service.estimate_fare(
        pickup_place_id="place_a",
        destination_place_id="place_b",
        vehicle_type="CAR_4",
    )
    assert "fare_amount" in res
    assert res["currency"] == "VND"
    assert res["fare_amount"] > 12000
