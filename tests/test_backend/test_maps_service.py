from __future__ import annotations

import pytest

from src.backend.config import Settings
from src.backend.maps.cache import InMemoryMapsCache
from src.backend.maps.contracts import PlaceCandidate, PlaceCandidateExpiredError, ResolvedPlace
from src.backend.maps.service_area import ServiceAreaChecker
from src.backend.services.maps_service import MapsService


class Geocoder:
    async def search(self, query: str, *, limit: int = 5):
        return [
            PlaceCandidate(
                provider_place_id="123",
                display_name="Bưu điện Hà Nội",
                formatted_address="Hoàn Kiếm, Hà Nội",
                latitude=21.0285,
                longitude=105.8542,
            )
        ]

    async def reverse(self, latitude: float, longitude: float):
        return None

    async def health_check(self):
        return {"status": "ok"}


class PlaceRepo:
    def __init__(self):
        self.rows: dict[str, ResolvedPlace] = {}

    async def find_place_by_provider(self, provider: str, provider_place_id: str):
        return next(
            (p for p in self.rows.values() if p.provider == provider and p.provider_place_id == provider_place_id), None
        )

    async def create_place(self, place: ResolvedPlace):
        self.rows[place.place_id] = place
        return place

    async def get_place(self, place_id: str):
        return self.rows.get(place_id)


@pytest.mark.asyncio
async def test_candidate_is_session_bound_and_server_owned() -> None:
    cache = InMemoryMapsCache()
    repo = PlaceRepo()
    service = MapsService(
        geocoding=Geocoder(),
        cache=cache,
        place_repo=repo,
        route_repo=repo,
        service_area=ServiceAreaChecker(),
        settings=Settings(app_env="test", maps_provider=""),
    )
    result = await service.search_places("bưu điện", session_id="ses_owner")
    candidate = result["candidates"][0]
    assert candidate["candidate_reference"].startswith("cand_")
    with pytest.raises(PlaceCandidateExpiredError):
        await service.resolve_place(provider="nominatim", provider_place_id="123", session_id="ses_attacker")
    resolved = await service.resolve_place(provider="nominatim", provider_place_id="123", session_id="ses_owner")
    assert resolved.latitude == 21.0285
    assert resolved.serviceable is True  # fail-open: no polygon → serviceable


@pytest.mark.asyncio
async def test_candidate_reference_resolves_only_after_selection() -> None:
    cache = InMemoryMapsCache()
    repo = PlaceRepo()
    service = MapsService(
        geocoding=Geocoder(),
        cache=cache,
        place_repo=repo,
        route_repo=repo,
        service_area=ServiceAreaChecker(),
        settings=Settings(app_env="test", maps_provider=""),
    )
    result = await service.search_places("bưu điện", session_id="ses_1")
    assert repo.rows == {}
    place = await service.resolve_candidate_reference(
        session_id="ses_1", candidate_reference=result["candidates"][0]["candidate_reference"]
    )
    assert repo.rows[place.place_id].display_name == "Bưu điện Hà Nội"
