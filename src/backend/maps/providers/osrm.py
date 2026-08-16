"""OSRM routing provider.

Implements ``RoutingProvider`` for OSRM's HTTP API.

CRITICAL: OSRM uses **longitude,latitude** coordinate ordering (§8).
The ``route`` method receives ``(lat, lon)`` from callers (standard GIS order)
and internally swaps to ``{lon},{lat}`` for the OSRM request.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from src.backend.maps.contracts import (
    InvalidRouteInputError,
    MapProviderTimeoutError,
    RouteNotFoundError,
    RouteProviderUnavailableError,
    RouteResult,
    TrafficDataStatus,
    validate_latitude,
    validate_longitude,
)
from src.backend.maps.providers.base import RoutingProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRYABLE_STATUS = {502, 503, 504}

# OSRM response codes that mean "no route"
_NO_ROUTE_CODES = {"NoRoute", "NoSegment"}


class OSRMProvider(RoutingProvider):
    """OSRM HTTP routing client.

    Parameters
    ----------
    base_url:
        Root URL of the OSRM instance (e.g. ``http://localhost:5000``).
    timeout:
        Request timeout in seconds.
    source_data_version:
        OSM data version string for provenance tracking.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:5000",
        timeout: float = 5.0,
        source_data_version: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._source_data_version = source_data_version

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> dict[str, Any]:
        """Execute a GET request with timeout and retry."""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url)

                if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    logger.warning(
                        "OSRM %s returned %d, retry %d/%d",
                        path, response.status_code, attempt + 1, _MAX_RETRIES,
                    )
                    continue

                if response.status_code >= 400:
                    raise RouteProviderUnavailableError(
                        f"OSRM returned HTTP {response.status_code}"
                    )

                data = response.json()
                if not isinstance(data, dict):
                    raise RouteProviderUnavailableError("OSRM returned non-object response")

                return data

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning("OSRM timeout, retry %d/%d", attempt + 1, _MAX_RETRIES)
                    continue
                raise MapProviderTimeoutError(f"OSRM timed out after {self._timeout}s") from exc

            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning("OSRM connection error, retry %d/%d", attempt + 1, _MAX_RETRIES)
                    continue
                raise RouteProviderUnavailableError(
                    f"Cannot connect to OSRM at {self._base_url}"
                ) from exc

            except (httpx.HTTPError, Exception) as exc:
                if isinstance(exc, (MapProviderTimeoutError, RouteProviderUnavailableError,
                                    RouteNotFoundError, InvalidRouteInputError)):
                    raise
                raise RouteProviderUnavailableError(f"OSRM request failed: {exc}") from exc

        raise RouteProviderUnavailableError(
            f"OSRM failed after {_MAX_RETRIES + 1} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route(
        self,
        pickup_lat: float,
        pickup_lon: float,
        dest_lat: float,
        dest_lon: float,
        *,
        profile: str = "driving",
    ) -> RouteResult:
        """Calculate a route between two points.

        OSRM coordinate ordering (§8): ``{longitude},{latitude}``
        """
        # Validate coordinates
        p_lat = validate_latitude(pickup_lat)
        p_lon = validate_longitude(pickup_lon)
        d_lat = validate_latitude(dest_lat)
        d_lon = validate_longitude(dest_lon)

        # CRITICAL: OSRM uses longitude,latitude ordering
        path = (
            f"/route/v1/{profile}/"
            f"{p_lon},{p_lat};{d_lon},{d_lat}"
            f"?overview=full&geometries=geojson&steps=false"
        )

        data = await self._get(path)

        # Handle OSRM error codes
        code = data.get("code", "")
        if code in _NO_ROUTE_CODES:
            raise RouteNotFoundError(
                f"OSRM: {code} — {data.get('message', 'No route found')}"
            )

        if code == "InvalidQuery":
            raise InvalidRouteInputError(
                f"OSRM: InvalidQuery — {data.get('message', 'Bad request')}"
            )

        if code != "Ok":
            raise RouteProviderUnavailableError(
                f"OSRM unexpected code: {code}"
            )

        # Extract route from response
        routes = data.get("routes", [])
        if not routes:
            raise RouteNotFoundError("OSRM returned empty routes array")

        best = routes[0]

        try:
            distance_meters = float(best["distance"])
            duration_seconds = float(best["duration"])
        except (KeyError, ValueError, TypeError) as exc:
            raise RouteProviderUnavailableError(
                f"OSRM malformed route data: {exc}"
            ) from exc

        geometry = best.get("geometry")

        now = datetime.now(UTC)
        route_id = f"rte_{uuid4().hex[:16]}"

        return RouteResult(
            route_id=route_id,
            pickup_place_id="",  # filled by caller
            destination_place_id="",  # filled by caller
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            geometry=geometry,
            # Vanilla OSRM has NO live traffic data (§9)
            traffic_status=TrafficDataStatus.NONE,
            traffic_timestamp=None,
            provider="osrm",
            provider_version="5.x",
            source_data_version=self._source_data_version,
            created_at=now,
        )

    async def health_check(self) -> dict[str, Any]:
        """Lightweight OSRM health check."""
        try:
            # Use a minimal route request to verify OSRM is operational
            # Hanoi coordinates — public/known POI, not PII
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self._base_url}/route/v1/driving/105.8542,21.0285;105.8543,21.0286"
                )
            return {
                "provider": "osrm",
                "status": "ok" if response.status_code == 200 else "degraded",
                "base_url": self._base_url,
                "http_status": response.status_code,
            }
        except Exception as exc:
            return {
                "provider": "osrm",
                "status": "failed",
                "base_url": self._base_url,
                "error": str(exc)[:200],
            }
