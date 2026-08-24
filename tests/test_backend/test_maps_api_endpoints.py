"""Unit and integration tests for Maps API endpoints (/api/v1/maps and /api/maps)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.main import app
from src.backend.maps.contracts import PlaceCandidate, RouteResult, TrafficDataStatus


@pytest.fixture
def mock_geocoding_search():
    candidate = PlaceCandidate(
        provider_place_id="998877",
        display_name="Đại học Bách Khoa Hà Nội, 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
        formatted_address="1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
        latitude=21.0074,
        longitude=105.8431,
        address={
            "road": "1 Đại Cồ Việt",
            "ward": "Bách Khoa",
            "district": "Hai Bà Trưng",
            "city": "Hà Nội",
            "country": "Việt Nam",
        },
        provider="nominatim",
    )
    return [candidate]


@pytest.fixture
def mock_geocoding_reverse():
    return PlaceCandidate(
        provider_place_id="112233",
        display_name="Hồ Hoàn Kiếm, Hoàn Kiếm, Hà Nội",
        formatted_address="Hoàn Kiếm, Hà Nội",
        latitude=21.0285,
        longitude=105.8542,
        provider="nominatim",
    )


@pytest.fixture
def mock_osrm_route():
    return RouteResult(
        route_id="rte_test12345678",
        pickup_place_id="plc_pickup",
        destination_place_id="plc_dest",
        distance_meters=3500.0,
        duration_seconds=540.0,
        geometry={
            "type": "LineString",
            "coordinates": [
                [105.8431, 21.0074],
                [105.8480, 21.0180],
                [105.8542, 21.0285],
            ],
        },
        legs=[{"distance": 3500.0, "duration": 540.0}],
        traffic_status=TrafficDataStatus.NONE,
        provider="osrm",
    )


@pytest.mark.asyncio
async def test_maps_search_endpoint(mock_geocoding_search):
    with patch("src.backend.maps.providers.nominatim.NominatimProvider.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_geocoding_search

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/maps/search?q=Bách Khoa&city=Hà Nội")
            assert resp.status_code == 200
            data = resp.json()
            assert data["query"] == "Bách Khoa"
            assert len(data["results"]) == 1
            item = data["results"][0]
            assert item["lat"] == 21.0074
            assert item["lon"] == 105.8431
            assert item["name"] == "Đại học Bách Khoa Hà Nội"
            assert item["address"]["city"] == "Hà Nội"


@pytest.mark.asyncio
async def test_maps_reverse_endpoint(mock_geocoding_reverse):
    with patch("src.backend.maps.providers.nominatim.NominatimProvider.reverse", new_callable=AsyncMock) as mock_rev:
        mock_rev.return_value = mock_geocoding_reverse

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/maps/reverse?lat=21.0285&lon=105.8542")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["results"]) == 1
            assert data["lat"] == 21.0285
            assert data["lon"] == 105.8542


@pytest.mark.asyncio
async def test_maps_route_with_coordinates(mock_osrm_route):
    with patch("src.backend.maps.providers.osrm.OSRMProvider.route", new_callable=AsyncMock) as mock_route:
        mock_route.return_value = mock_osrm_route

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "pickup": {"lat": 21.0074, "lon": 105.8431},
                "destination": {"lat": 21.0285, "lon": 105.8542},
                "profile": "driving",
            }
            resp = await client.post("/api/v1/maps/route", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["distance_m"] == 3500.0
            assert data["distance_km"] == 3.5
            assert data["duration_s"] == 540.0
            assert data["duration_minutes"] == 9
            assert data["geometry"]["type"] == "LineString"
            assert len(data["geometry"]["coordinates"]) == 3


@pytest.mark.asyncio
async def test_maps_resolve_trip_endpoint(mock_geocoding_search, mock_geocoding_reverse, mock_osrm_route):
    with patch("src.backend.maps.providers.nominatim.NominatimProvider.search", new_callable=AsyncMock) as mock_search, \
         patch("src.backend.maps.providers.osrm.OSRMProvider.route", new_callable=AsyncMock) as mock_route:
        mock_search.return_value = mock_geocoding_search
        mock_route.return_value = mock_osrm_route

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "pickup": "Bách Khoa",
                "destination": "Hồ Gươm",
                "city": "Hà Nội",
            }
            resp = await client.post("/api/v1/maps/resolve-trip", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert "pickup" in data
            assert "destination" in data
            assert "route" in data
            assert data["route"]["distance_km"] == 3.5
            assert data["route"]["duration_minutes"] == 9


@pytest.mark.asyncio
async def test_maps_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/maps/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded", "not_configured")


@pytest.mark.asyncio
async def test_direct_api_maps_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/maps/health")
        assert resp.status_code == 200
