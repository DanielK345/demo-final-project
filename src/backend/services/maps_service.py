"""Maps orchestration with provider isolation, session-bound candidates and durable snapshots."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from src.backend.config import Settings, get_settings
from src.backend.maps.cache import (
    InMemoryMapsCache,
    MapsCacheProvider,
    RedisMapsCache,
    candidate_cache_key,
    candidate_reference_key,
    route_cache_key,
    search_cache_key,
)
from src.backend.maps.contracts import (
    MapProviderUnavailableError,
    MapsDomainError,
    PlaceCandidateExpiredError,
    PlaceNotFoundError,
    PlaceResolutionStatus,
    ResolvedPlace,
    RouteResult,
    ServiceAreaNotConfiguredError,
    TrafficDataStatus,
    validate_latitude,
    validate_longitude,
)
from src.backend.maps.providers.base import GeocodingProvider, RoutingProvider
from src.backend.maps.providers.factory import get_geocoding_provider, get_routing_provider
from src.backend.maps.service_area import ServiceAreaChecker
from src.backend.repositories.maps_repository import MapsRepository

logger = logging.getLogger(__name__)


class MapsService:
    """Single Maps boundary used by API and backend tool executors."""

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
        self._geocoding = geocoding or (get_geocoding_provider(self._settings) if self._provider_configured else None)
        self._routing = routing or (get_routing_provider(self._settings) if self._provider_configured else None)
        self._service_area = service_area or ServiceAreaChecker(
            geojson_path=self._settings.maps_service_area_path,
            service_area_id=self._settings.maps_service_area_id,
        )
        if cache is not None:
            self._cache = cache
        elif self._settings.maps_cache_backend == "redis":
            self._cache = RedisMapsCache(self._settings.maps_cache_redis_url)
        else:
            self._cache = InMemoryMapsCache()
        durable = MapsRepository() if self._settings.app_env != "test" else None
        self._place_repo = place_repo or durable
        self._route_repo = route_repo or durable

    async def _remember_candidates(self, candidates: list[dict[str, Any]], session_id: str) -> list[dict[str, Any]]:
        remembered: list[dict[str, Any]] = []
        for original in candidates:
            candidate = dict(original)
            if session_id:
                reference = (
                    "cand_"
                    + hashlib.sha256(
                        f"{session_id}:{candidate['provider']}:{candidate['provider_place_id']}".encode()
                    ).hexdigest()[:24]
                )
                candidate["candidate_reference"] = reference
                await self._cache.set(
                    candidate_cache_key(session_id, str(candidate["provider"]), str(candidate["provider_place_id"])),
                    candidate,
                    ttl_seconds=self._settings.map_candidate_ttl_seconds,
                )
                await self._cache.set(
                    candidate_reference_key(session_id, reference),
                    candidate,
                    ttl_seconds=self._settings.map_candidate_ttl_seconds,
                )
            remembered.append(candidate)
        return remembered

    async def search_places(self, query: str, *, session_id: str = "", limit: int | None = None) -> dict[str, Any]:
        if self._geocoding is None:
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }
        effective_limit = limit or self._settings.map_search_limit
        started = time.monotonic()
        try:
            key = search_cache_key(
                query,
                country=self._settings.map_country_code,
                provider=self._settings.geocoding_provider,
                data_version=self._settings.osm_data_version,
            )
            result = await self._cache.get(key)
            if result is None:
                candidates = await self._geocoding.search(query, limit=effective_limit)
                api_candidates = [candidate.to_api_dict() for candidate in candidates]
                result = {
                    "query": query,
                    "status": PlaceResolutionStatus.CANDIDATES.value
                    if api_candidates
                    else PlaceResolutionStatus.NOT_FOUND.value,
                    "candidates": api_candidates,
                }
                await self._cache.set(key, result, ttl_seconds=300)
            result = dict(result)
            result["candidates"] = await self._remember_candidates(list(result.get("candidates", [])), session_id)
            return result
        except MapsDomainError as exc:
            logger.warning("maps.search_failed code=%s", exc.code)
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": exc.code,
            }
        finally:
            logger.info("maps.search latency_seconds=%.3f", time.monotonic() - started)

    async def reverse_geocode(self, latitude: float, longitude: float, *, session_id: str = "") -> dict[str, Any]:
        if self._geocoding is None:
            return {
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }
        lat, lon = validate_latitude(latitude), validate_longitude(longitude)
        started = time.monotonic()
        try:
            candidate = await self._geocoding.reverse(lat, lon)
            candidates = [candidate.to_api_dict()] if candidate else []
            candidates = await self._remember_candidates(candidates, session_id)
            return {
                "latitude": lat,
                "longitude": lon,
                "status": PlaceResolutionStatus.CANDIDATES.value
                if candidates
                else PlaceResolutionStatus.NOT_FOUND.value,
                "candidates": candidates,
            }
        except MapsDomainError as exc:
            return {
                "latitude": lat,
                "longitude": lon,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "candidates": [],
                "error": exc.code,
            }
        finally:
            logger.info("maps.reverse latency_seconds=%.3f", time.monotonic() - started)

    async def resolve_place(self, *, provider: str, provider_place_id: str, session_id: str) -> ResolvedPlace:
        if self._place_repo is not None:
            existing = await self._place_repo.find_place_by_provider(provider, provider_place_id)
            if existing is not None:
                return existing
        candidate = await self._cache.get(candidate_cache_key(session_id, provider, provider_place_id))
        if candidate is None:
            raise PlaceCandidateExpiredError()
        if (
            str(candidate.get("provider", "")).casefold() != provider.casefold()
            or str(candidate.get("provider_place_id")) != provider_place_id
        ):
            raise PlaceNotFoundError("Candidate identity does not match provider result")
        lat = validate_latitude(float(candidate["latitude"]))
        lon = validate_longitude(float(candidate["longitude"]))
        if self._settings.app_env == "production" and not self._service_area.configured:
            raise ServiceAreaNotConfiguredError()
        area = self._service_area.check(lat, lon)
        place = ResolvedPlace(
            place_id=f"plc_{uuid4().hex[:16]}",
            provider=provider.casefold(),
            provider_place_id=provider_place_id,
            display_name=str(candidate["display_name"]),
            formatted_address=str(candidate.get("formatted_address", "")),
            latitude=lat,
            longitude=lon,
            types=list(candidate.get("types", [])),
            serviceable=area.serviceable,
            service_area_id=area.service_area_id,
            source_version=self._settings.osm_data_version or None,
            resolved_at=datetime.now(UTC),
        )
        return await self._place_repo.create_place(place) if self._place_repo is not None else place

    async def resolve_candidate_reference(self, *, session_id: str, candidate_reference: str) -> ResolvedPlace:
        candidate = await self._cache.get(candidate_reference_key(session_id, candidate_reference))
        if candidate is None:
            raise PlaceCandidateExpiredError()
        return await self.resolve_place(
            provider=str(candidate["provider"]),
            provider_place_id=str(candidate["provider_place_id"]),
            session_id=session_id,
        )

    @staticmethod
    def _route_from_cache(
        data: dict[str, Any], pickup_place_id: str, destination_place_id: str, ttl: int
    ) -> RouteResult:
        now = datetime.now(UTC)
        return RouteResult(
            route_id=f"rte_{uuid4().hex[:16]}",
            pickup_place_id=pickup_place_id,
            destination_place_id=destination_place_id,
            distance_meters=float(data["distance_meters"]),
            duration_seconds=float(data["duration_seconds"]),
            geometry=data.get("geometry"),
            traffic_status=TrafficDataStatus(str(data.get("traffic_status", "NONE"))),
            traffic_timestamp=data.get("traffic_timestamp"),
            provider=str(data["provider"]),
            provider_version=str(data.get("provider_version", "")),
            source_data_version=str(data.get("source_data_version", "")),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )

    async def create_route(self, *, pickup_place_id: str, destination_place_id: str) -> RouteResult:
        if self._routing is None:
            raise MapProviderUnavailableError("Routing provider not configured")
        pickup, destination = await self._get_place(pickup_place_id), await self._get_place(destination_place_id)
        if pickup is None or destination is None:
            raise PlaceNotFoundError("Pickup or destination place does not exist")
        if pickup.serviceable is False or destination.serviceable is False:
            from src.backend.maps.contracts import OutOfServiceAreaError

            raise OutOfServiceAreaError()
        started = time.monotonic()
        try:
            key = route_cache_key(
                pickup.latitude,
                pickup.longitude,
                destination.latitude,
                destination.longitude,
                provider=self._settings.routing_provider,
                data_version=self._settings.osm_data_version,
            )
            cached = await self._cache.get(key)
            if cached is not None:
                route = self._route_from_cache(
                    cached, pickup_place_id, destination_place_id, self._settings.map_route_ttl_seconds
                )
            else:
                route = await self._routing.route(
                    pickup.latitude, pickup.longitude, destination.latitude, destination.longitude
                )
                route.pickup_place_id, route.destination_place_id = pickup_place_id, destination_place_id
                await self._cache.set(key, route.to_snapshot_dict(), ttl_seconds=self._settings.map_route_ttl_seconds)
            if self._route_repo is not None:
                await self._route_repo.create_route_snapshot(route)
            return route
        except MapsDomainError:
            raise
        except Exception as exc:
            raise MapProviderUnavailableError(f"Route creation failed: {exc}") from exc
        finally:
            logger.info("maps.route latency_seconds=%.3f", time.monotonic() - started)

    async def _get_place(self, place_id: str) -> ResolvedPlace | None:
        return await self._place_repo.get_place(place_id) if self._place_repo is not None else None

    async def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "maps_configured": self._provider_configured,
            "service_area_configured": self._service_area.configured,
        }
        if self._geocoding is not None:
            result["geocoding"] = await self._geocoding.health_check()
        if self._routing is not None:
            result["routing"] = await self._routing.health_check()
        if isinstance(self._cache, RedisMapsCache):
            try:
                result["cache"] = "ok" if await self._cache.health_check() else "failed"
            except Exception:
                result["cache"] = "failed"
        else:
            result["cache"] = "memory_dev_only"
        return result
