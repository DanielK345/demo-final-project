"""Unit tests for NominatimProvider (§38) — response parsing, no result, invalid result."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.backend.maps.providers.nominatim import NominatimProvider


@pytest.fixture
def provider():
    return NominatimProvider(base_url="http://test-nominatim:8088", timeout=2.0)


class TestQueryValidation:
    """Input validation (§14, §18)."""

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="empty"):
            NominatimProvider._validate_query("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            NominatimProvider._validate_query("   ")

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="maximum length"):
            NominatimProvider._validate_query("x" * 501)

    def test_unicode_normalised(self):
        result = NominatimProvider._validate_query("  Hà Nội  ")
        assert result == "Hà Nội"


class TestResponseParsing:
    """Nominatim JSON v2 response parsing (§38)."""

    def test_valid_result(self):
        raw = {
            "place_id": 12345,
            "lat": "21.0285",
            "lon": "105.8542",
            "display_name": "Bưu điện Hà Nội, Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
            "category": "amenity",
            "type": "post_office",
            "address": {
                "road": "Đinh Tiên Hoàng",
                "city_district": "Hoàn Kiếm",
                "city": "Hà Nội",
                "country": "Việt Nam",
            },
        }
        candidate = NominatimProvider._to_candidate(raw)
        assert candidate is not None
        assert candidate.provider_place_id == "12345"
        assert candidate.latitude == 21.0285
        assert candidate.longitude == 105.8542
        assert candidate.provider == "nominatim"
        assert "amenity" in candidate.types

    def test_missing_lat_returns_none(self):
        raw = {"place_id": 1, "lon": "105.0", "display_name": "Test"}
        assert NominatimProvider._to_candidate(raw) is None

    def test_missing_display_name_returns_none(self):
        raw = {"place_id": 1, "lat": "21.0", "lon": "105.0", "display_name": ""}
        assert NominatimProvider._to_candidate(raw) is None

    def test_missing_place_id_returns_none(self):
        raw = {"lat": "21.0", "lon": "105.0", "display_name": "Test"}
        # place_id absent but osm_id may be there
        candidate = NominatimProvider._to_candidate(raw)
        # With no place_id and no osm_id, should return None
        assert candidate is None

    def test_invalid_lat_returns_none(self):
        raw = {"place_id": 1, "lat": "invalid", "lon": "105.0", "display_name": "Test"}
        assert NominatimProvider._to_candidate(raw) is None


class TestSearch:
    """Search method (§14)."""

    @pytest.mark.asyncio
    async def test_empty_results(self, provider: NominatimProvider):
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=[]):
            result = await provider.search("nonexistent place xyz123")
            assert result == []

    @pytest.mark.asyncio
    async def test_valid_results(self, provider: NominatimProvider):
        mock_data = [
            {"place_id": 1, "lat": "21.0", "lon": "105.0",
             "display_name": "Test Place", "category": "amenity", "type": "cafe"},
        ]
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await provider.search("test")
            assert len(result) == 1
            assert result[0].display_name == "Test Place"

    @pytest.mark.asyncio
    async def test_non_list_response(self, provider: NominatimProvider):
        """Malformed response should return empty list, not crash."""
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value={"error": "bad"}):
            result = await provider.search("test")
            assert result == []


class TestReverse:
    """Reverse geocoding (§15, §38)."""

    @pytest.mark.asyncio
    async def test_valid_reverse(self, provider: NominatimProvider):
        mock_data = {
            "place_id": 1, "lat": "21.0285", "lon": "105.8542",
            "display_name": "Hoàn Kiếm, Hà Nội",
        }
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=mock_data):
            result = await provider.reverse(21.0285, 105.8542)
            assert result is not None
            assert result.latitude == 21.0285

    @pytest.mark.asyncio
    async def test_reverse_no_result(self, provider: NominatimProvider):
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value={"error": "Unable to geocode"}):
            result = await provider.reverse(0.0, 0.0)
            assert result is None

    @pytest.mark.asyncio
    async def test_reverse_invalid_lat(self, provider: NominatimProvider):
        from src.backend.maps.contracts import InvalidRouteInputError
        with pytest.raises(InvalidRouteInputError, match="Latitude"):
            await provider.reverse(91.0, 105.0)


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_ok(self, provider: NominatimProvider):
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value={"status": 0}):
            result = await provider.health_check()
            assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_failed(self, provider: NominatimProvider):
        with patch.object(provider, "_get", new_callable=AsyncMock, side_effect=Exception("down")):
            result = await provider.health_check()
            assert result["status"] == "failed"
