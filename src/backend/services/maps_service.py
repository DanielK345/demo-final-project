"""Maps orchestration service — the single entry point for geocoding, routing
and place resolution.

All Maps operations flow through this service. Public API routes call
``MapsService``; no direct Nominatim/OSRM access from outside this module.

Responsibilities:
- Search places via geocoding provider
- Reverse-geocode coordinates
- Resolve a candidate into a persisted internal Place
- Create immutable route snapshots via routing provider
- Check service area
- Cache provider calls
- Emit observability metrics
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.backend.config import Settings, get_settings
from src.backend.maps.cache import InMemoryMapsCache, MapsCacheProvider, route_cache_key, search_cache_key
from src.backend.maps.contracts import (
    MapProviderUnavailableError,
    MapsDomainError,
    OutOfServiceAreaError,
    PlaceNotFoundError,
    PlaceResolutionStatus,
    ResolvedPlace,
    RouteResult,
    validate_latitude,
    validate_longitude,
)
from src.backend.maps.providers.base import GeocodingProvider, RoutingProvider
from src.backend.maps.providers.factory import get_geocoding_provider, get_routing_provider
from src.backend.maps.service_area import ServiceAreaChecker
from src.backend.repositories.maps_repository import MapsRepository

logger = logging.getLogger(__name__)


class MapsService:
    """Orchestrates geocoding, routing, service-area and persistence.

    The service is designed to work in two modes:
    1. **Provider configured** (``maps_provider`` is set): calls Nominatim/OSRM
    2. **No provider**: falls back to existing gazetteer/demo behaviour

    Persistence (PlaceRepository, RouteSnapshotRepository) is injected optionally.
    When None, the service operates statelessly (suitable for search/reverse).
    """

    def __init__(
        self,
        *,
        geocoding: GeocodingProvider | None = None,
        routing: RoutingProvider | None = None,
        service_area: ServiceAreaChecker | None = None,
        cache: MapsCacheProvider | None = None,
        settings: Settings | None = None,
        place_repo: Any = None,
        route_repo: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider_configured = bool(self._settings.maps_provider)

        if self._provider_configured:
            self._geocoding = geocoding or get_geocoding_provider(self._settings)
            self._routing = routing or get_routing_provider(self._settings)
        else:
            self._geocoding = geocoding
            self._routing = routing

        self._service_area = service_area or ServiceAreaChecker(
            geojson_path=self._settings.maps_service_area_path,
            service_area_id=self._settings.maps_service_area_id,
        )
        self._cache = cache or InMemoryMapsCache()
        durable_repository = MapsRepository() if self._settings.app_env != "test" else None
        self._place_repo = place_repo or durable_repository
        self._route_repo = route_repo or durable_repository

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search_places(
        self,
        query: str,
        *,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search for places matching *query*.

        Returns a dict with ``status`` and ``candidates`` suitable for the
        public API response.
        """
        if self._geocoding is None:
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }

        effective_limit = limit or self._settings.map_search_limit
        start = time.monotonic()

        try:
            # Check cache
            cache_key = search_cache_key(
                query,
                country=self._settings.map_country_code,
                provider=self._settings.geocoding_provider,
                data_version=self._settings.osm_data_version,
            )
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

            candidates = await self._geocoding.search(query, limit=effective_limit)

            if not candidates:
                result: dict[str, Any] = {
                    "query": query,
                    "status": PlaceResolutionStatus.NOT_FOUND.value,
                    "candidates": [],
                }
            elif len(candidates) == 1:
                # Single result — still CANDIDATES, not auto-RESOLVED (§17)
                result = {
                    "query": query,
                    "status": PlaceResolutionStatus.CANDIDATES.value,
                    "candidates": [c.to_api_dict() for c in candidates],
                }
            else:
                result = {
                    "query": query,
                    "status": PlaceResolutionStatus.CANDIDATES.value,
                    "candidates": [c.to_api_dict() for c in candidates],
                }

            await self._cache.set(cache_key, result, ttl_seconds=300)
            return result

        except MapsDomainError as exc:
            logger.warning("Maps search failed for query='%s': %s", query[:50], exc.code)
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": exc.code,
            }
        finally:
            elapsed = time.monotonic() - start
            logger.info("maps.search query=%r latency=%.3fs", query[:50], elapsed)

    # ------------------------------------------------------------------
    # Reverse
    # ------------------------------------------------------------------

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Reverse-geocode coordinates to a place."""
        if self._geocoding is None:
            return {
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }

        lat = validate_latitude(latitude)
        lon = validate_longitude(longitude)
        start = time.monotonic()

        try:
            candidate = await self._geocoding.reverse(lat, lon)
            if candidate is None:
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "status": PlaceResolutionStatus.NOT_FOUND.value,
                    "candidates": [],
                }

            return {
                "latitude": lat,
                "longitude": lon,
                "status": PlaceResolutionStatus.CANDIDATES.value,
                "candidates": [candidate.to_api_dict()],
            }

        except MapsDomainError as exc:
            logger.warning("Maps reverse failed: %s", exc.code)
            return {
                "latitude": lat,
                "longitude": lon,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": exc.code,
            }
        finally:
            elapsed = time.monotonic() - start
            logger.info("maps.reverse lat=%.4f lon=%.4f latency=%.3fs", latitude, longitude, elapsed)

    # ------------------------------------------------------------------
    # Place resolution (§17, §25)
    # ------------------------------------------------------------------

    async def resolve_place(
        self,
        *,
        provider: str,
        provider_place_id: str,
        session_id: str,
        candidate_data: dict[str, Any] | None = None,
    ) -> ResolvedPlace:
        """Confirm a candidate and persist as an internal Place.

        1. Validate the candidate exists (from search cache or re-fetch)
        2. Persist with internal ``plc_<uuid>`` ID
        3. Check service area
        4. Return ``ResolvedPlace``
        """
        # Check if already resolved in DB
        if self._place_repo is not None:
            existing = await self._place_repo.find_place_by_provider(provider, provider_place_id)
            if existing is not None:
                return existing

        if candidate_data is None:
            raise PlaceNotFoundError("Candidate data not provided and not found in cache")

        # Generate internal place_id
        place_id = f"plc_{uuid4().hex[:16]}"

        lat = float(candidate_data.get("latitude", 0))
        lon = float(candidate_data.get("longitude", 0))

        # Check service area
        area_result = self._service_area.check(lat, lon)

        resolved = ResolvedPlace(
            place_id=place_id,
            provider=provider,
            provider_place_id=provider_place_id,
            display_name=str(candidate_data.get("display_name", "")),
            formatted_address=str(candidate_data.get("formatted_address", "")),
            latitude=lat,
            longitude=lon,
            types=candidate_data.get("types", []),
            serviceable=area_result.serviceable,
            service_area_id=area_result.service_area_id,
            source_version=self._settings.osm_data_version or None,
            resolved_at=datetime.now(UTC),
        )

        # Persist
        if self._place_repo is not None:
            await self._place_repo.create_place(resolved)

        logger.info(
            "Place resolved: id=%s provider=%s serviceable=%s",
            place_id,
            provider,
            area_result.serviceable,
        )

        return resolved

    # ------------------------------------------------------------------
    # Routing (§26)
    # ------------------------------------------------------------------

    async def create_route(
        self,
        *,
        pickup_place_id: str,
        destination_place_id: str,
    ) -> RouteResult:
        """Create a route between two resolved places.

        1. Load places from repository
        2. Verify both exist and are serviceable
        3. Call routing provider with lat/lon from DB
        4. Persist immutable route snapshot
        5. Return normalised RouteResult
        """
        if self._routing is None:
            raise MapProviderUnavailableError("Routing provider not configured")

        # Load places
        pickup = await self._get_place(pickup_place_id)
        destination = await self._get_place(destination_place_id)

        if pickup is None:
            raise PlaceNotFoundError(f"Pickup place not found: {pickup_place_id}")
        if destination is None:
            raise PlaceNotFoundError(f"Destination place not found: {destination_place_id}")

        # Verify serviceable
        if pickup.serviceable is False:
            raise OutOfServiceAreaError("Pickup location is outside service area")
        if destination.serviceable is False:
            raise OutOfServiceAreaError("Destination is outside service area")

        start = time.monotonic()

        try:
            # Check cache
            cache_key = route_cache_key(
                pickup.latitude,
                pickup.longitude,
                destination.latitude,
                destination.longitude,
                provider=self._settings.routing_provider,
                data_version=self._settings.osm_data_version,
            )
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

            # Call routing provider
            route = await self._routing.route(
                pickup.latitude,
                pickup.longitude,
                destination.latitude,
                destination.longitude,
            )

            # Fill place IDs
            route.pickup_place_id = pickup_place_id
            route.destination_place_id = destination_place_id

            # Persist snapshot (immutable — §22)
            if self._route_repo is not None:
                await self._route_repo.create_route_snapshot(route)

            # Cache
            await self._cache.set(cache_key, route, ttl_seconds=300)

            return route

        except MapsDomainError:
            raise
        except Exception as exc:
            raise MapProviderUnavailableError(f"Route creation failed: {exc}") from exc
        finally:
            elapsed = time.monotonic() - start
            logger.info(
                "maps.route pickup=%s dest=%s latency=%.3fs",
                pickup_place_id[:16],
                destination_place_id[:16],
                elapsed,
            )

    async def _get_place(self, place_id: str) -> ResolvedPlace | None:
        """Load a resolved place from the repository."""
        if self._place_repo is not None:
            return await self._place_repo.get_place(place_id)
        return None

    # ------------------------------------------------------------------
    # Health (§37)
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Check health of all configured providers."""
        result: dict[str, Any] = {"maps_configured": self._provider_configured}

        if self._geocoding is not None:
            result["geocoding"] = await self._geocoding.health_check()

        if self._routing is not None:
            result["routing"] = await self._routing.health_check()

        result["service_area_configured"] = self._service_area.configured

        return result
