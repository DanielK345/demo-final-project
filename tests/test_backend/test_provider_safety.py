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
