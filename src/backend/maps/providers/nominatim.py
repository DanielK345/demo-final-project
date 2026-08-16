"""Nominatim geocoding provider — self-hosted or public (DEV ONLY).

Implements ``GeocodingProvider`` for Nominatim's JSON v2 API.

Production MUST use a self-hosted Nominatim instance (see ``infra/maps/nominatim/``).
The public ``nominatim.openstreetmap.org`` is acceptable only during development and
MUST be clearly labelled DEV_ONLY with appropriate User-Agent.

Vietnamese search specifics (§18):
- ``countrycodes=vn`` limits results to Vietnam
- ``accept-language=vi`` preferred for Vietnamese display names
- Accent/no-accent and mixed-case queries are handled by Nominatim natively
"""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

import httpx

from src.backend.maps.contracts import (
    MapProviderTimeoutError,
    MapProviderUnavailableError,
    PlaceCandidate,
    validate_latitude,
    validate_longitude,
)
from src.backend.maps.providers.base import GeocodingProvider

logger = logging.getLogger(__name__)

# httpx transport-level retry budget
_MAX_RETRIES = 2
_RETRYABLE_STATUS = {502, 503, 504}


class NominatimProvider(GeocodingProvider):
    """Nominatim JSON v2 geocoding client.

    Parameters
    ----------
    base_url:
        Root URL of the Nominatim instance (e.g. ``http://localhost:8088``).
    timeout:
        Request timeout in seconds.
    country_code:
        ISO 3166-1 alpha-2 country code for search filtering.
    language:
        Preferred display language (BCP-47).
    """

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8088",
        timeout: float = 5.0,
        country_code: str = "vn",
        language: str = "vi",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._country_code = country_code
        self._language = language
        # Respect OSM usage policy (§51) — identify the application
        self._headers = {
            "User-Agent": "AloSM/1.0 (ride-hailing; contact: ops@alosm.vn)",
            "Accept-Language": language,
        }

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_query(query: str) -> str:
        """Validate and normalise a search query (§14, §18)."""
        if not isinstance(query, str):
            raise ValueError("Search query must be a string")
        cleaned = unicodedata.normalize("NFC", query.strip())
        if len(cleaned) < 1:
            raise ValueError("Search query must not be empty")
        if len(cleaned) > 500:
            raise ValueError("Search query exceeds maximum length (500 chars)")
        return cleaned

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, str]) -> Any:
        """Execute a GET request with timeout and retry for transient errors."""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    headers=self._headers,
                ) as client:
                    response = await client.get(url, params=params)

                if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    logger.warning(
                        "Nominatim %s returned %d, retry %d/%d",
                        path, response.status_code, attempt + 1, _MAX_RETRIES,
                    )
                    continue

                if response.status_code >= 400:
                    raise MapProviderUnavailableError(
                        f"Nominatim returned HTTP {response.status_code}"
                    )

                return response.json()

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning("Nominatim timeout on %s, retry %d/%d", path, attempt + 1, _MAX_RETRIES)
                    continue
                raise MapProviderTimeoutError(f"Nominatim timed out after {self._timeout}s") from exc

            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning("Nominatim connection error on %s, retry %d/%d", path, attempt + 1, _MAX_RETRIES)
                    continue
                raise MapProviderUnavailableError(
                    f"Cannot connect to Nominatim at {self._base_url}"
                ) from exc

            except (httpx.HTTPError, Exception) as exc:
                if isinstance(exc, (MapProviderTimeoutError, MapProviderUnavailableError)):
                    raise
                raise MapProviderUnavailableError(f"Nominatim request failed: {exc}") from exc

        # Should not reach here, but safety net
        raise MapProviderUnavailableError(f"Nominatim failed after {_MAX_RETRIES + 1} attempts") from last_exc

    # ------------------------------------------------------------------
    # Response normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _to_candidate(raw: dict[str, Any]) -> PlaceCandidate | None:
        """Convert a Nominatim JSON v2 result to a ``PlaceCandidate``."""
        try:
            lat = float(raw["lat"])
            lon = float(raw["lon"])
        except (KeyError, ValueError, TypeError):
            return None

        display_name = str(raw.get("display_name", ""))
        if not display_name:
            return None

        # Build formatted address from addressdetails when available
        address_parts = raw.get("address", {})
        formatted = display_name  # fallback to display_name
        if address_parts:
            parts = []
            for key in ("house_number", "road", "suburb", "quarter", "city_district",
                        "city", "state", "postcode", "country"):
                val = address_parts.get(key)
                if val:
                    parts.append(str(val))
            if parts:
                formatted = ", ".join(parts)

        # Determine types from 'category' and 'type' fields
        types: list[str] = []
        if raw.get("category"):
            types.append(str(raw["category"]))
        if raw.get("type"):
            types.append(str(raw["type"]))

        # Use Nominatim's own place_id as provider_place_id (as string)
        provider_place_id = str(raw.get("place_id", raw.get("osm_id", "")))
        if not provider_place_id:
            return None

        return PlaceCandidate(
            provider_place_id=provider_place_id,
            display_name=display_name,
            formatted_address=formatted,
            latitude=lat,
            longitude=lon,
            types=types,
            provider="nominatim",
            provider_payload_version="jsonv2",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, query: str, *, limit: int = 5) -> list[PlaceCandidate]:
        """Search for places matching *query* (§14)."""
        clean_query = self._validate_query(query)

        params: dict[str, str] = {
            "q": clean_query,
            "format": "jsonv2",
            "addressdetails": "1",
            "limit": str(min(limit, 20)),
            "countrycodes": self._country_code,
        }

        data = await self._get("/search", params)

        if not isinstance(data, list):
            logger.warning("Nominatim search returned non-list: %s", type(data))
            return []

        candidates: list[PlaceCandidate] = []
        for raw in data:
            candidate = self._to_candidate(raw)
            if candidate is not None:
                candidates.append(candidate)

        return candidates

    async def reverse(self, latitude: float, longitude: float) -> PlaceCandidate | None:
        """Reverse-geocode coordinates to the nearest place (§15)."""
        lat = validate_latitude(latitude)
        lon = validate_longitude(longitude)

        params: dict[str, str] = {
            "lat": str(lat),
            "lon": str(lon),
            "format": "jsonv2",
            "addressdetails": "1",
        }

        try:
            data = await self._get("/reverse", params)
        except MapProviderUnavailableError:
            raise
        except Exception:
            return None

        if not isinstance(data, dict) or "error" in data:
            return None

        return self._to_candidate(data)

    async def health_check(self) -> dict[str, Any]:
        """Check Nominatim health via /status endpoint (§13)."""
        try:
            data = await self._get("/status", {"format": "json"})
            return {
                "provider": "nominatim",
                "status": "ok" if isinstance(data, dict) and data.get("status") == 0 else "degraded",
                "base_url": self._base_url,
                "raw": data if isinstance(data, dict) else {},
            }
        except Exception as exc:
            return {
                "provider": "nominatim",
                "status": "failed",
                "base_url": self._base_url,
                "error": str(exc)[:200],
            }
