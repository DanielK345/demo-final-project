from src.agents.core.booking import BookingData
from src.agents.core.booking.state import (
    clear_fare_estimate,
    clear_vehicle_selection,
    reduce_place_result,
)
from src.agents.core.booking_types import VehicleType
from src.agents.tools.schemas import SearchPlaceResult, VehicleOption


def selected_booking_data() -> BookingData:
    option = VehicleOption(
        option_id="car-7",
        vehicle_type=VehicleType.CAR_7,
        display_name="Ô tô 7 chỗ",
        capacity=7,
        luggage_capacity=3,
        estimate_id="fare-001",
        fare_amount=105000,
        currency="VND",
        eta_minutes=6,
    )
    return BookingData(
        vehicle_type=VehicleType.CAR_7,
        selected_vehicle_option_id=option.option_id,
        vehicle_display_name=option.display_name,
        vehicle_options=[option],
        recommended_vehicle_option_id=option.option_id,
        fare_estimate_id=option.estimate_id,
        estimated_fare_amount=option.fare_amount,
        estimated_currency=option.currency,
        estimated_eta_minutes=option.eta_minutes,
        estimated_distance_km=12.5,
    )


def test_clear_vehicle_selection_does_not_mutate_source() -> None:
    original = selected_booking_data()

    updated = clear_vehicle_selection(original)

    assert original.vehicle_type == VehicleType.CAR_7.value
    assert original.selected_vehicle_option_id == "car-7"
    assert updated.vehicle_type is None
    assert updated.selected_vehicle_option_id is None
    assert updated.vehicle_options == []
    assert updated.fare_estimate_id == "fare-001"


def test_clear_fare_estimate_only_removes_stale_quote() -> None:
    original = selected_booking_data()

    updated = clear_fare_estimate(original)

    assert original.fare_estimate_id == "fare-001"
    assert updated.vehicle_type == VehicleType.CAR_7.value
    assert updated.fare_estimate_id is None
    assert updated.estimated_fare_amount is None
    assert updated.estimated_eta_minutes is None


def test_reduce_place_result_keeps_source_immutable() -> None:
    original = BookingData(
        pickup={"place_id": "old", "display_name": "Địa chỉ cũ"}
    )
    result = SearchPlaceResult.model_validate(
        {
            "candidates": [
                {"place_id": "new", "display_name": "Địa chỉ mới"}
            ]
        }
    )

    reduction = reduce_place_result(original, result, pickup=True)

    assert original.pickup is not None
    assert original.pickup.place_id == "old"
    assert reduction.data.pickup is not None
    assert reduction.data.pickup.place_id == "new"
