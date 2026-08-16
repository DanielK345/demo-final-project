"""Unit tests for Maps domain contracts, coordinate validation, and state machine (§38)."""

from __future__ import annotations

import pytest

from src.backend.maps.contracts import (
    InvalidRouteInputError,
    MapProviderTimeoutError,
    MapsDomainError,
    PlaceCandidate,
    PlaceNotFoundError,
    PlaceResolutionStatus,
    ResolvedPlace,
    RouteNotFoundError,
    RouteResult,
    TrafficDataStatus,
    validate_latitude,
    validate_longitude,
)


class TestCoordinateValidation:
    """Latitude and longitude validation (§38)."""

    def test_valid_latitude(self):
        assert validate_latitude(21.0285) == 21.0285

    def test_valid_latitude_boundary(self):
        assert validate_latitude(-90) == -90
        assert validate_latitude(90) == 90

    def test_invalid_latitude_too_high(self):
        with pytest.raises(InvalidRouteInputError, match="Latitude"):
            validate_latitude(91)

    def test_invalid_latitude_too_low(self):
        with pytest.raises(InvalidRouteInputError, match="Latitude"):
            validate_latitude(-91)

    def test_valid_longitude(self):
        assert validate_longitude(105.8542) == 105.8542

    def test_valid_longitude_boundary(self):
        assert validate_longitude(-180) == -180
        assert validate_longitude(180) == 180

    def test_invalid_longitude_too_high(self):
        with pytest.raises(InvalidRouteInputError, match="Longitude"):
            validate_longitude(181)

    def test_invalid_longitude_too_low(self):
        with pytest.raises(InvalidRouteInputError, match="Longitude"):
            validate_longitude(-181)


class TestPlaceCandidate:
    def test_to_api_dict_excludes_internal_fields(self):
        c = PlaceCandidate(
            provider_place_id="12345",
            display_name="Bưu điện Hà Nội",
            formatted_address="1 Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
            latitude=21.0285,
            longitude=105.8542,
            types=["amenity", "post_office"],
            provider="nominatim",
            provider_payload_version="jsonv2",
        )
        api = c.to_api_dict()
        assert "provider_place_id" in api
        assert "display_name" in api
        assert "latitude" in api
        # Internal version not exposed
        assert "provider_payload_version" not in api


class TestResolvedPlace:
    def test_to_api_dict_contains_place_id(self):
        p = ResolvedPlace(
            place_id="plc_abc123",
            provider="nominatim",
            provider_place_id="12345",
            display_name="Test",
            formatted_address="Test Address",
            latitude=21.0,
            longitude=105.0,
        )
        api = p.to_api_dict()
        assert api["place_id"] == "plc_abc123"
        assert "provider_place_id" not in api  # internal detail hidden


class TestRouteResult:
    def test_vanilla_osrm_not_live_traffic(self):
        """Vanilla OSRM must NOT label as LIVE_TRAFFIC (§9)."""
        r = RouteResult(
            route_id="rte_test",
            pickup_place_id="plc_a",
            destination_place_id="plc_b",
            distance_meters=5000,
            duration_seconds=600,
            provider="osrm",
        )
        assert r.traffic_status == TrafficDataStatus.NONE
        api = r.to_api_dict()
        assert api["traffic_status"] == "NONE"


class TestPlaceResolutionStatus:
    """Place resolution state machine (§17, §38)."""

    def test_all_states_exist(self):
        expected = {"UNRESOLVED", "CANDIDATES", "RESOLVED", "AMBIGUOUS",
                    "NOT_FOUND", "OUT_OF_SERVICE_AREA", "PROVIDER_ERROR"}
        actual = {s.value for s in PlaceResolutionStatus}
        assert expected == actual

    def test_candidates_not_auto_resolved(self):
        """CANDIDATES != RESOLVED — user confirmation required."""
        assert PlaceResolutionStatus.CANDIDATES != PlaceResolutionStatus.RESOLVED


class TestDomainErrors:
    def test_route_not_found_is_not_retryable(self):
        e = RouteNotFoundError()
        assert e.code == "ROUTE_NOT_FOUND"
        assert e.retryable is False

    def test_timeout_is_retryable(self):
        e = MapProviderTimeoutError()
        assert e.code == "MAP_PROVIDER_TIMEOUT"
        assert e.retryable is True

    def test_place_not_found(self):
        e = PlaceNotFoundError()
        assert e.code == "PLACE_NOT_FOUND"
        assert e.retryable is False

    def test_domain_error_inheritance(self):
        e = RouteNotFoundError()
        assert isinstance(e, MapsDomainError)
        assert isinstance(e, Exception)
