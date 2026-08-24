from pathlib import Path

import pytest

from src.backend.services.pricing_catalog import DEFAULT_PRICING_PATH, load_pricing_catalog
from src.backend.services.pricing_service import PricingService, calculate_distance_fare


def test_repository_pricing_catalog_is_versioned_validated_and_demo_only():
    catalog = load_pricing_catalog()

    assert DEFAULT_PRICING_PATH == Path("data/pricing/hanoi_demo_2026-08-16.yaml").resolve()
    assert catalog.version == "2026-08-16"
    assert catalog.region == "HAN"
    assert catalog.status == "DEMO"
    assert catalog.data_quality == "DEMO"
    assert catalog.source_sha256 == "6AFF08BD3DAFD6C8833F423D9CEC6DAE1F74E60932EA3696B3096C6B97315718"
    assert set(catalog.vehicles) == {"MOTORBIKE", "CAR_4", "CAR_7", "LUXURY"}
    assert catalog.cancellation_policy.status == "DEMO"


@pytest.mark.parametrize(
    ("distance_km", "expected_fare"),
    [(2, 30_500), (3, 45_200), (13, 191_300), (26, 368_800)],
)
def test_progressive_car4_distance_tiers(distance_km, expected_fare):
    pricing = load_pricing_catalog().vehicles["CAR_4"]
    assert calculate_distance_fare(distance_km, pricing) == expected_fare


def test_quote_preserves_provenance_and_does_not_invent_surcharges():
    quote = PricingService().estimate_fare(
        pickup_place_id="pickup",
        destination_place_id="destination",
        vehicle_type="LUXURY",
    )

    assert quote["pricing_version"] == "2026-08-16"
    assert quote["pricing_region"] == "HAN"
    assert quote["pricing_status"] == "DEMO"
    assert quote["data_quality"] == "DEMO"
    assert quote["source_type"] == "PUBLIC_REFERENCE"
    assert quote["fare_breakdown"]["time_fare"] == 0
    assert quote["fare_breakdown"]["surcharge_amount"] == 0
    assert quote["fare_breakdown"]["applied_surcharges"] == []


def test_vehicle_options_come_from_catalog_and_apply_capacity_filters():
    options = PricingService().vehicle_options(
        pickup_place_id="pickup",
        destination_place_id="destination",
        passenger_count=5,
        luggage_count=3,
    )
    by_type = {option["vehicle_type"]: option for option in options}

    assert set(by_type) == {"MOTORBIKE", "CAR_4", "CAR_7", "LUXURY"}
    assert by_type["CAR_7"]["available"] is True
    assert by_type["MOTORBIKE"]["available"] is False
    assert by_type["LUXURY"]["available"] is False
    assert all(option["pricing_status"] == "DEMO" for option in options)


def test_catalog_loader_fails_closed_for_invalid_tiers(tmp_path):
    invalid = tmp_path / "invalid.yaml"
    text = DEFAULT_PRICING_PATH.read_text(encoding="utf-8").replace(
        "- {up_to_km: null, per_km: 11900}",
        "- {up_to_km: 30, per_km: 11900}",
        1,
    )
    invalid.write_text(text, encoding="utf-8")

    with pytest.raises(RuntimeError, match="final distance tier must be unbounded"):
        load_pricing_catalog(invalid)
