from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


class MapsProviderUnavailableError(RuntimeError):
    """Raised when no approved maps/routing provider is configured."""


@dataclass(frozen=True, slots=True)
class Place:
    place_id: str
    display_name: str
    formatted_address: str
    latitude: float
    longitude: float
    types: tuple[str, ...]
    serviceable: bool
    provider: str
    provider_payload_version: str


@dataclass(frozen=True, slots=True)
class Route:
    route_id: str
    pickup_place_id: str
    destination_place_id: str
    distance_meters: int
    duration_seconds: int
    polyline: str | None
    traffic_timestamp: datetime | None
    provider: str
    provider_payload_version: str


@runtime_checkable
class MapsProvider(Protocol):
    async def geocode(self, query: str, *, limit: int = 5) -> list[Place]: ...

    async def reverse_geocode(self, latitude: float, longitude: float) -> list[Place]: ...

    async def autocomplete(self, query: str, *, limit: int = 5) -> list[Place]: ...

    async def route(self, pickup_place_id: str, destination_place_id: str) -> Route: ...


class UnavailableMapsProvider:
    """Fail-closed production default. It never manufactures places or routes."""

    def __init__(self, reason_code: str = "MAPS_PROVIDER_NOT_CONFIGURED") -> None:
        self.reason_code = reason_code

    def _raise(self) -> None:
        raise MapsProviderUnavailableError(self.reason_code)

    async def geocode(self, query: str, *, limit: int = 5) -> list[Place]:
        self._raise()

    async def reverse_geocode(self, latitude: float, longitude: float) -> list[Place]:
        self._raise()

    async def autocomplete(self, query: str, *, limit: int = 5) -> list[Place]:
        self._raise()

    async def route(self, pickup_place_id: str, destination_place_id: str) -> Route:
        self._raise()


class MapsClient:
    """Provider-neutral adapter; defaults to unavailable instead of fake coordinates."""

    def __init__(self, provider: MapsProvider | None = None) -> None:
        self.provider = provider or UnavailableMapsProvider()

    async def geocode(self, query: str, *, limit: int = 5) -> list[Place]:
        normalized = query.strip()
        if not normalized:
            return []
        return await self.provider.geocode(normalized, limit=limit)

    async def reverse_geocode(self, latitude: float, longitude: float) -> list[Place]:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("coordinates outside WGS84 bounds")
        return await self.provider.reverse_geocode(latitude, longitude)

    async def autocomplete(self, query: str, *, limit: int = 5) -> list[Place]:
        normalized = query.strip()
        if not normalized:
            return []
        return await self.provider.autocomplete(normalized, limit=limit)

    async def route(self, pickup_place_id: str, destination_place_id: str) -> Route:
        if not pickup_place_id.strip() or not destination_place_id.strip():
            raise ValueError("resolved pickup and destination place IDs are required")
        return await self.provider.route(pickup_place_id, destination_place_id)
