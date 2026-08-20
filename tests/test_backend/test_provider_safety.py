import pytest

from src.backend.integrations.maps_client import MapsClient, MapsProviderUnavailableError
from src.backend.services.place_search_service import PlaceSearchService
from src.backend.services.pricing_service import PricingService


@pytest.mark.asyncio
async def test_maps_default_fails_closed_without_manufacturing_coordinates():
    with pytest.raises(MapsProviderUnavailableError, match="MAPS_PROVIDER_NOT_CONFIGURED"):
        await MapsClient().geocode("1 Nguyễn Huệ")


def test_unknown_free_form_address_is_not_marked_resolved_by_gazetteer():
    assert PlaceSearchService().search("999 đường hoàn toàn không có") == []


def test_hanoi_gazetteer_requires_specific_vinuni_and_ho_guom_points():
    service = PlaceSearchService()

    pickup = service.search("VinUni")
    destination = service.search("Hồ Gươm")

    assert [item["display_name"] for item in pickup] == [
        "Cổng chính VinUni",
        "Cổng phụ VinUni",
        "Cổng ký túc xá VinUni",
    ]
    assert [item["display_name"] for item in destination] == [
        "Đền Ngọc Sơn",
        "Bưu điện Hà Nội",
        "Quảng trường Đông Kinh Nghĩa Thục",
        "Tượng đài Vua Lý Thái Tổ",
    ]
    assert all(item["provider"] == "local_landmark_mock" for item in pickup + destination)
    assert all(item["parent_landmark"] in {"VinUni", "Hồ Gươm"} for item in pickup + destination)
    assert all(item["address"] and item["google_maps_url"] for item in pickup + destination)
    assert "cổng thành cũng" in pickup[0]["asr_aliases"]
    assert "cũng chính bin Uni" in pickup[0]["asr_aliases"]


def test_hanoi_gazetteer_resolves_known_aliases_to_canonical_places():
    service = PlaceSearchService()

    assert service.search("VinUniversity")[0]["parent_landmark"] == "VinUni"
    assert service.search("Hồ Gương")[0]["parent_landmark"] == "Hồ Gươm"


def test_other_hanoi_landmarks_keep_the_single_result_flow():
    results = PlaceSearchService().search("Lăng Chủ tịch Hồ Chí Minh")

    assert len(results) == 1
    assert results[0]["display_name"] == "Lăng Chủ tịch Hồ Chí Minh"
    assert results[0]["provider"] == "local_gazetteer"


def test_demo_quote_is_versioned_expiring_and_explicitly_labeled():
    quote = PricingService().estimate_fare(
        pickup_place_id="place_pickup",
        destination_place_id="place_destination",
        vehicle_type="CAR_4",
    )
    assert quote["pricing_version"]
    assert quote["expires_at"] > quote["issued_at"]
    assert quote["estimated"] is True
    assert quote["data_quality"] == "DEMO"


def test_unknown_vehicle_type_is_rejected_instead_of_silently_using_car4_price():
    with pytest.raises(ValueError, match="Unknown vehicle type"):
        PricingService().estimate_fare(
            pickup_place_id="place_pickup",
            destination_place_id="place_destination",
            vehicle_type="SPACESHIP",
        )
