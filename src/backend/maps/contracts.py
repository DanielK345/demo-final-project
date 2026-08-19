"""Domain contracts for the Maps subsystem.

Every provider implementation normalises its raw response into these contracts
before returning data to the service layer. No raw provider payload ever leaks
to public API consumers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Place resolution state machine (§17)
# ---------------------------------------------------------------------------


class PlaceResolutionStatus(StrEnum):
    """Lifecycle of a place during a booking session.

    Flow: UNRESOLVED → CANDIDATES → (user selects) → RESOLVED
    Error branches: NOT_FOUND, AMBIGUOUS, OUT_OF_SERVICE_AREA, PROVIDER_ERROR
    """

    UNRESOLVED = "UNRESOLVED"
    CANDIDATES = "CANDIDATES"
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    OUT_OF_SERVICE_AREA = "OUT_OF_SERVICE_AREA"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class TrafficDataStatus(StrEnum):
    """Provenance label for route duration estimates."""

    NONE = "NONE"  # vanilla OSRM, no traffic data
    LIVE_TRAFFIC = "LIVE_TRAFFIC"  # only when provider actually has live traffic
    HISTORICAL = "HISTORICAL"  # historical speed profiles


# ---------------------------------------------------------------------------
# Place contracts
# ---------------------------------------------------------------------------


class PlaceCandidate:
    """A geocoding result not yet confirmed by the user.

    Candidates carry ``provider_place_id`` (the provider's native ID) but NOT an
    internal ``place_id`` — the internal ID is assigned only upon resolution.
    """

    __slots__ = (
        "provider_place_id",
        "display_name",
        "formatted_address",
        "latitude",
        "longitude",
        "types",
        "provider",
        "provider_payload_version",
    )

    def __init__(
        self,
        *,
        provider_place_id: str,
        display_name: str,
        formatted_address: str,
        latitude: float,
        longitude: float,
        types: list[str] | None = None,
        provider: str = "nominatim",
        provider_payload_version: str = "",
    ) -> None:
        self.provider_place_id = provider_place_id
        self.display_name = display_name
        self.formatted_address = formatted_address
        self.latitude = latitude
        self.longitude = longitude
        self.types = types or []
        self.provider = provider
        self.provider_payload_version = provider_payload_version

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise for public API response — no internal DB fields exposed."""
        return {
            "provider_place_id": self.provider_place_id,
            "display_name": self.display_name,
            "formatted_address": self.formatted_address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "types": self.types,
            "provider": self.provider,
        }


class ResolvedPlace:
    """A place that has been confirmed by the user and persisted.

    ``place_id`` is the internal AloSM identifier (``plc_<uuid>``); systems MUST
    NOT depend on the provider's integer ``place_id`` (e.g. Nominatim's).
    """

    __slots__ = (
        "place_id",
        "provider",
        "provider_place_id",
        "display_name",
        "formatted_address",
        "latitude",
        "longitude",
        "types",
        "serviceable",
        "service_area_id",
        "source_version",
        "resolved_at",
    )

    def __init__(
        self,
        *,
        place_id: str,
        provider: str,
        provider_place_id: str,
        display_name: str,
        formatted_address: str,
        latitude: float,
        longitude: float,
        types: list[str] | None = None,
        serviceable: bool | None = None,
        service_area_id: str | None = None,
        source_version: str | None = None,
        resolved_at: datetime | None = None,
    ) -> None:
        self.place_id = place_id
        self.provider = provider
        self.provider_place_id = provider_place_id
        self.display_name = display_name
        self.formatted_address = formatted_address
        self.latitude = latitude
        self.longitude = longitude
        self.types = types or []
        self.serviceable = serviceable
        self.service_area_id = service_area_id
        self.source_version = source_version
        self.resolved_at = resolved_at

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "place_id": self.place_id,
            "display_name": self.display_name,
            "formatted_address": self.formatted_address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "types": self.types,
            "serviceable": self.serviceable,
            "service_area_id": self.service_area_id,
            "provider": self.provider,
        }


# ---------------------------------------------------------------------------
# Route contract (§9)
# ---------------------------------------------------------------------------


class RouteResult:
    """Normalised routing result from any provider."""

    __slots__ = (
        "route_id",
        "pickup_place_id",
        "destination_place_id",
        "distance_meters",
        "duration_seconds",
        "geometry",
        "traffic_status",
        "traffic_timestamp",
        "provider",
        "provider_version",
        "source_data_version",
        "created_at",
        "expires_at",
    )

    def __init__(
        self,
        *,
        route_id: str,
        pickup_place_id: str,
        destination_place_id: str,
        distance_meters: float,
        duration_seconds: float,
        geometry: dict[str, Any] | None = None,
        traffic_status: TrafficDataStatus = TrafficDataStatus.NONE,
        traffic_timestamp: str | None = None,
        provider: str = "osrm",
        provider_version: str = "",
        source_data_version: str = "",
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        self.route_id = route_id
        self.pickup_place_id = pickup_place_id
        self.destination_place_id = destination_place_id
        self.distance_meters = distance_meters
        self.duration_seconds = duration_seconds
        self.geometry = geometry
        self.traffic_status = traffic_status
        self.traffic_timestamp = traffic_timestamp
        self.provider = provider
        self.provider_version = provider_version
        self.source_data_version = source_data_version
        self.created_at = created_at
        self.expires_at = expires_at

    def to_api_dict(self) -> dict[str, Any]:
        """Public API representation — no internal DB IDs leaked."""
        return {
            "route_id": self.route_id,
            "distance_meters": self.distance_meters,
            "duration_seconds": self.duration_seconds,
            "geometry": self.geometry,
            "traffic_status": self.traffic_status.value,
            "provider": self.provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def to_snapshot_dict(self) -> dict[str, Any]:
        """Full dict for DB persistence."""
        return {
            "route_id": self.route_id,
            "pickup_place_id": self.pickup_place_id,
            "destination_place_id": self.destination_place_id,
            "distance_meters": self.distance_meters,
            "duration_seconds": self.duration_seconds,
            "geometry": self.geometry,
            "traffic_status": self.traffic_status.value,
            "traffic_timestamp": self.traffic_timestamp,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "source_data_version": self.source_data_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


# ---------------------------------------------------------------------------
# Domain errors (§10)
# ---------------------------------------------------------------------------


class MapsDomainError(Exception):
    """Base error for all Maps subsystem failures."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{code}] {message}")


class RouteNotFoundError(MapsDomainError):
    def __init__(self, message: str = "No route found between the given locations") -> None:
        super().__init__("ROUTE_NOT_FOUND", message, retryable=False)


class RouteProviderUnavailableError(MapsDomainError):
    def __init__(self, message: str = "Routing provider is unavailable") -> None:
        super().__init__("ROUTE_PROVIDER_UNAVAILABLE", message, retryable=True)


class InvalidRouteInputError(MapsDomainError):
    def __init__(self, message: str = "Invalid input for route calculation") -> None:
        super().__init__("INVALID_ROUTE_INPUT", message, retryable=False)


class MapProviderTimeoutError(MapsDomainError):
    def __init__(self, message: str = "Map provider request timed out") -> None:
        super().__init__("MAP_PROVIDER_TIMEOUT", message, retryable=True)


class PlaceCandidateExpiredError(MapsDomainError):
    def __init__(self, message: str = "Place candidate expired; search again") -> None:
        super().__init__("PLACE_CANDIDATE_EXPIRED", message, retryable=False)


class PlaceNotFoundError(MapsDomainError):
    def __init__(self, message: str = "Place not found") -> None:
        super().__init__("PLACE_NOT_FOUND", message, retryable=False)


class MapProviderUnavailableError(MapsDomainError):
    def __init__(self, message: str = "Map provider is unavailable") -> None:
        super().__init__("MAP_PROVIDER_UNAVAILABLE", message, retryable=True)


class ServiceAreaNotConfiguredError(MapsDomainError):
    def __init__(self, message: str = "Service area not configured") -> None:
        super().__init__("SERVICE_AREA_NOT_CONFIGURED", message, retryable=False)


class OutOfServiceAreaError(MapsDomainError):
    def __init__(self, message: str = "Location is outside the service area") -> None:
        super().__init__("OUT_OF_SERVICE_AREA", message, retryable=False)


# ---------------------------------------------------------------------------
# Coordinate validation helpers
# ---------------------------------------------------------------------------


def validate_latitude(lat: float) -> float:
    """Validate and return latitude in [-90, 90]."""
    if not isinstance(lat, (int, float)) or lat < -90 or lat > 90:
        raise InvalidRouteInputError(f"Latitude must be between -90 and 90, got {lat}")
    return float(lat)


def validate_longitude(lon: float) -> float:
    """Validate and return longitude in [-180, 180]."""
    if not isinstance(lon, (int, float)) or lon < -180 or lon > 180:
        raise InvalidRouteInputError(f"Longitude must be between -180 and 180, got {lon}")
    return float(lon)
