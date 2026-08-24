"""Maps cache abstraction.

Provides a provider cache interface and a development-only in-memory
implementation. Production distributed cache (Redis) is configurable but
not auto-enabled — this in-memory cache is NOT production-ready.
"""

from __future__ import annotations

import abc
import hashlib
import json
import time
import unicodedata
from typing import Any

from redis.asyncio import Redis


class MapsCacheProvider(abc.ABC):
    """Abstract cache interface for Maps results."""

    @abc.abstractmethod
    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value, or ``None`` if expired/missing."""

    @abc.abstractmethod
    async def set(self, key: str, value: Any, *, ttl_seconds: int = 300) -> None:
        """Store a value with a TTL."""


class InMemoryMapsCache(MapsCacheProvider):
    """Process-memory cache for development only.

    NOT production-ready — no eviction strategy, no distributed sharing,
    no size limit enforcement beyond max_entries.
    """

    def __init__(self, *, max_entries: int = 1000) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._max_entries = max_entries

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, *, ttl_seconds: int = 300) -> None:
        # Simple eviction: clear oldest when full
        if len(self._store) >= self._max_entries:
            # Remove ~25% oldest entries
            sorted_keys = sorted(self._store, key=lambda k: self._store[k][0])
            for k in sorted_keys[: self._max_entries // 4]:
                del self._store[k]
        self._store[key] = (time.monotonic() + ttl_seconds, value)


class RedisMapsCache(MapsCacheProvider):
    """Distributed JSON cache for multi-instance Maps deployments."""

    def __init__(self, url: str) -> None:
        if not url:
            raise ValueError("MAPS_CACHE_REDIS_URL_REQUIRED")
        self._client = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: Any, *, ttl_seconds: int = 300) -> None:
        await self._client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

    async def health_check(self) -> bool:
        return bool(await self._client.ping())


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def search_cache_key(
    query: str,
    *,
    country: str = "vn",
    language: str = "vi",
    provider: str = "nominatim",
    data_version: str = "",
) -> str:
    """Build a deterministic cache key for search results."""
    normalised = unicodedata.normalize("NFC", query.strip().casefold())
    raw = f"search:{provider}:{country}:{language}:{data_version}:{normalised}"
    return f"maps:search:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def route_cache_key(
    pickup_lat: float,
    pickup_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    profile: str = "driving",
    provider: str = "osrm",
    data_version: str = "",
) -> str:
    """Build a deterministic cache key for route results.

    Coordinates are rounded to ~11m precision (4 decimal places) to allow
    cache hits for nearby coordinates.
    """
    raw = f"route:{provider}:{profile}:{data_version}:{pickup_lat:.4f},{pickup_lon:.4f};{dest_lat:.4f},{dest_lon:.4f}"
    return f"maps:route:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def candidate_cache_key(session_id: str, provider: str, provider_place_id: str) -> str:
    """Return a session-bound opaque cache key for an unconfirmed candidate."""
    raw = f"candidate:{session_id}:{provider.casefold()}:{provider_place_id}"
    return f"maps:candidate:{hashlib.sha256(raw.encode()).hexdigest()}"


def candidate_reference_key(session_id: str, candidate_reference: str) -> str:
    raw = f"candidate-reference:{session_id}:{candidate_reference}"
    return f"maps:candidate-ref:{hashlib.sha256(raw.encode()).hexdigest()}"
