from unittest.mock import AsyncMock, patch

import pytest

from src.backend.maps.contracts import InvalidRouteInputError, RouteNotFoundError
from src.backend.maps.providers.osrm import OSRMProvider


@pytest.mark.asyncio
async def test_osrm_uses_longitude_latitude_order_and_normalizes_route() -> None:
    provider = OSRMProvider(base_url="http://osrm", source_data_version="vn-2026-08", route_ttl_seconds=120)
    payload = {
        "code": "Ok",
        "routes": [{"distance": 8500.5, "duration": 1380.0, "geometry": {"type": "LineString", "coordinates": []}}],
    }
    with patch.object(provider, "_get", new_callable=AsyncMock, return_value=payload) as get:
        route = await provider.route(21.0285, 105.8542, 21.0278, 105.8341)
    path = get.await_args.args[0]
    assert "105.8542,21.0285;105.8341,21.0278" in path
    assert route.distance_meters == 8500.5
    assert route.duration_seconds == 1380.0
    assert route.traffic_status.value == "NONE"
    assert route.expires_at is not None and route.expires_at > route.created_at


@pytest.mark.asyncio
async def test_osrm_maps_no_route() -> None:
    provider = OSRMProvider(base_url="http://osrm")
    with patch.object(provider, "_get", new_callable=AsyncMock, return_value={"code": "NoRoute", "message": "none"}):
        with pytest.raises(RouteNotFoundError):
            await provider.route(21.0, 105.0, 21.1, 105.1)


@pytest.mark.asyncio
async def test_osrm_rejects_swapped_invalid_latitude() -> None:
    provider = OSRMProvider(base_url="http://osrm")
    with pytest.raises(InvalidRouteInputError):
        await provider.route(105.8542, 21.0285, 21.0278, 105.8341)
