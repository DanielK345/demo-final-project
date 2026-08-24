"""Abstract base classes for geocoding and routing providers.

Designed so that future providers (Goong, VietMap, Google, Mapbox) can be
added without modifying the Agent/business layer — only a new subclass and a
factory entry are needed.
"""

from __future__ import annotations

import abc
from typing import Any

from src.backend.maps.contracts import PlaceCandidate, RouteResult


class GeocodingProvider(abc.ABC):
    """Geocoding abstraction — search by text and reverse by coordinates."""

    @abc.abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[PlaceCandidate]:
        """Search for places matching *query*; return up to *limit* candidates."""

    @abc.abstractmethod
    async def reverse(self, latitude: float, longitude: float) -> PlaceCandidate | None:
        """Reverse-geocode coordinates to the nearest place, or ``None``."""

    @abc.abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return provider health status."""


class RoutingProvider(abc.ABC):
    """Routing abstraction — compute a route between two points."""

    @abc.abstractmethod
    async def route(
        self,
        pickup_lat: float,
        pickup_lon: float,
        dest_lat: float,
        dest_lon: float,
        *,
        profile: str = "driving",
    ) -> RouteResult:
        """Calculate a route and return a normalised ``RouteResult``."""

    @abc.abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return provider health status."""
