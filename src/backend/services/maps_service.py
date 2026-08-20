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

    async def search_places(
        self,
        query: str,
        *,
        session_id: str = "",
        limit: int | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        if self._geocoding is None:
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "results": [],
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }
        effective_limit = limit or self._settings.map_search_limit
        started = time.monotonic()
        try:
            key = search_cache_key(
                f"{query}:{city or ''}",
                country=self._settings.map_country_code,
                provider=self._settings.geocoding_provider,
                data_version=self._settings.osm_data_version,
            )
            result = await self._cache.get(key)
            if result is None:
                try:
                    candidates = await self._geocoding.search(query, limit=effective_limit, city=city)
                except TypeError:
                    candidates = await self._geocoding.search(query, limit=effective_limit)
                api_candidates = [candidate.to_api_dict() for candidate in candidates]
                result = {
                    "query": query,
                    "status": PlaceResolutionStatus.CANDIDATES.value
                    if api_candidates
                    else PlaceResolutionStatus.NOT_FOUND.value,
                    "results": api_candidates,
                    "candidates": api_candidates,
                }
                await self._cache.set(key, result, ttl_seconds=self._settings.map_cache_ttl_seconds)
            result = dict(result)
            remembered = await self._remember_candidates(list(result.get("candidates", [])), session_id)
            result["candidates"] = remembered
            result["results"] = remembered
            return result
        except MapsDomainError as exc:
            logger.warning("maps.search_failed code=%s", exc.code)
            return {
                "query": query,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "results": [],
                "candidates": [],
                "error": exc.code,
            }
        finally:
            logger.info("maps.search latency_seconds=%.3f", time.monotonic() - started)

    async def reverse_geocode(self, latitude: float, longitude: float, *, session_id: str = "") -> dict[str, Any]:
        if self._geocoding is None:
            return {
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "results": [],
                "candidates": [],
                "error": "MAP_PROVIDER_NOT_CONFIGURED",
            }
        lat, lon = validate_latitude(latitude), validate_longitude(longitude)
        started = time.monotonic()
        try:
            candidate = await self._geocoding.reverse(lat, lon)
            candidates = [candidate.to_api_dict()] if candidate else []
            remembered = await self._remember_candidates(candidates, session_id)
            return {
                "latitude": lat,
                "longitude": lon,
                "lat": lat,
                "lon": lon,
                "status": PlaceResolutionStatus.CANDIDATES.value
                if remembered
                else PlaceResolutionStatus.NOT_FOUND.value,
                "results": remembered,
                "candidates": remembered,
            }
        except MapsDomainError as exc:
            return {
                "latitude": lat,
                "longitude": lon,
                "lat": lat,
                "lon": lon,
                "status": PlaceResolutionStatus.PROVIDER_ERROR.value,
                "results": [],
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
            name=str(candidate.get("name", "")),
            display_name=str(candidate["display_name"]),
            formatted_address=str(candidate.get("formatted_address", "")),
            latitude=lat,
            longitude=lon,
            address=candidate.get("address"),
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
            legs=data.get("legs", []),
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

    async def create_route_coordinates(
        self,
        pickup_lat: float,
        pickup_lon: float,
        dest_lat: float,
        dest_lon: float,
        *,
        profile: str = "driving",
    ) -> RouteResult:
        if self._routing is None:
            raise MapProviderUnavailableError("Routing provider not configured")
        p_lat = validate_latitude(pickup_lat)
        p_lon = validate_longitude(pickup_lon)
        d_lat = validate_latitude(dest_lat)
        d_lon = validate_longitude(dest_lon)

        started = time.monotonic()
        try:
            key = route_cache_key(
                p_lat,
                p_lon,
                d_lat,
                d_lon,
                provider=f"{self._settings.routing_provider}:{profile}",
                data_version=self._settings.osm_data_version,
            )
            cached = await self._cache.get(key)
            if cached is not None:
                return self._route_from_cache(cached, "", "", self._settings.map_route_ttl_seconds)
            route = await self._routing.route(p_lat, p_lon, d_lat, d_lon, profile=profile)
            await self._cache.set(key, route.to_snapshot_dict(), ttl_seconds=self._settings.map_route_ttl_seconds)
            return route
        except MapsDomainError:
            raise
        except Exception as exc:
            raise MapProviderUnavailableError(f"Route calculation failed: {exc}") from exc
        finally:
            logger.info("maps.route_coords latency_seconds=%.3f", time.monotonic() - started)

    async def resolve_trip(
        self,
        pickup: str | dict[str, Any],
        destination: str | dict[str, Any],
        *,
        city: str = "Hà Nội",
        session_id: str = "",
    ) -> dict[str, Any]:
        """Resolve pickup and destination locations and calculate the connecting road route."""
        # 1. Resolve pickup
        if isinstance(pickup, dict) and "lat" in pickup and "lon" in pickup:
            p_lat, p_lon = float(pickup["lat"]), float(pickup["lon"])
            p_res = await self.reverse_geocode(p_lat, p_lon, session_id=session_id)
            p_item = p_res["results"][0] if p_res.get("results") else {
                "id": f"coords:{p_lat},{p_lon}",
                "name": f"{p_lat:.4f}, {p_lon:.4f}",
                "display_name": f"{p_lat:.4f}, {p_lon:.4f}",
                "lat": p_lat,
                "lon": p_lon,
                "latitude": p_lat,
                "longitude": p_lon,
                "provider": "custom",
            }
        else:
            p_query = str(pickup).strip()
            p_search = await self.search_places(p_query, session_id=session_id, city=city, limit=1)
            if not p_search.get("results"):
                raise PlaceNotFoundError(f"Không tìm thấy điểm đón: {p_query}")
            p_item = p_search["results"][0]

        # 2. Resolve destination
        if isinstance(destination, dict) and "lat" in destination and "lon" in destination:
            d_lat, d_lon = float(destination["lat"]), float(destination["lon"])
            d_res = await self.reverse_geocode(d_lat, d_lon, session_id=session_id)
            d_item = d_res["results"][0] if d_res.get("results") else {
                "id": f"coords:{d_lat},{d_lon}",
                "name": f"{d_lat:.4f}, {d_lon:.4f}",
                "display_name": f"{d_lat:.4f}, {d_lon:.4f}",
                "lat": d_lat,
                "lon": d_lon,
                "latitude": d_lat,
                "longitude": d_lon,
                "provider": "custom",
            }
        else:
            d_query = str(destination).strip()
            d_search = await self.search_places(d_query, session_id=session_id, city=city, limit=1)
            if not d_search.get("results"):
                raise PlaceNotFoundError(f"Không tìm thấy điểm đến: {d_query}")
            d_item = d_search["results"][0]

        # 3. Calculate road route
        route = await self.create_route_coordinates(
            pickup_lat=float(p_item["lat"]),
            pickup_lon=float(p_item["lon"]),
            dest_lat=float(d_item["lat"]),
            dest_lon=float(d_item["lon"]),
        )

        return {
            "pickup": p_item,
            "destination": d_item,
            "route": route.to_api_dict(),
        }

    async def _get_place(self, place_id: str) -> ResolvedPlace | None:
        return await self._place_repo.get_place(place_id) if self._place_repo is not None else None

    async def health_check(self) -> dict[str, Any]:
        status_value = "ok" if self._provider_configured else "not_configured"
        result: dict[str, Any] = {
            "status": status_value,
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
