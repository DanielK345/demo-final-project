"""Maps public API endpoints (§23, §24, §25, §26).

All endpoints are prefixed with ``/api/v1`` (via router include in ``__init__.py``).
Frontend MUST NOT call Nominatim/OSRM directly (§2 architecture).

Endpoints:
    GET  /places/search?q=...          — search for places
    GET  /places/reverse?lat=...&lon=... — reverse-geocode
    POST /places/resolve               — confirm and persist a candidate
    POST /routes                       — create route between resolved places
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.api.routes.sessions import _require_session_access
from src.backend.maps.contracts import (
    MapsDomainError,
    OutOfServiceAreaError,
    PlaceNotFoundError,
    RouteNotFoundError,
)
from src.backend.services.maps_service import MapsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["maps"])
route_router = APIRouter(prefix="/routes", tags=["maps"])

# Lazy singleton — instantiated on first request
_maps_service: MapsService | None = None


def _get_maps_service() -> MapsService:
    global _maps_service
    if _maps_service is None:
        _maps_service = MapsService()
    return _maps_service


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class PlaceResolveRequest(BaseModel):
    provider: str = Field(..., description="Geocoding provider name (e.g. 'nominatim')")
    provider_place_id: str = Field(..., description="Provider's native place ID")
    session_id: str = Field(..., description="Current session ID")
    # Optional candidate data if not cached server-side
    display_name: str = ""
    formatted_address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    types: list[str] = Field(default_factory=list)


class RouteRequest(BaseModel):
    session_id: str = Field(..., description="Authenticated booking session")
    pickup_place_id: str = Field(..., description="Internal place ID for pickup")
    destination_place_id: str = Field(..., description="Internal place ID for destination")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_places(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(default=5, ge=1, le=20, description="Max results"),
) -> dict[str, Any]:
    """Search for places matching the query (§23).

    Response:
        {"query": "...", "status": "CANDIDATES", "candidates": [...]}
    """
    service = _get_maps_service()
    result = await service.search_places(q, limit=limit)
    return result


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
) -> dict[str, Any]:
    """Reverse-geocode coordinates (§24).

    Response consistent with search. Returns PLACE_NOT_FOUND, not HTTP 500.
    """
    service = _get_maps_service()
    result = await service.reverse_geocode(lat, lon)
    return result


@router.post("/resolve")
async def resolve_place(
    request: PlaceResolveRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Confirm a candidate and persist as an internal Place (§25).

    Returns the internal ``place_id`` after validation and service-area check.
    """
    await _require_session_access(request.session_id, authorization)
    service = _get_maps_service()

    candidate_data = {
        "display_name": request.display_name,
        "formatted_address": request.formatted_address,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "types": request.types,
    }

    try:
        resolved = await service.resolve_place(
            provider=request.provider,
            provider_place_id=request.provider_place_id,
            session_id=request.session_id,
            candidate_data=candidate_data if request.display_name else None,
        )
        return resolved.to_api_dict()

    except OutOfServiceAreaError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
    except PlaceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
    except MapsDomainError as exc:
        status = 503 if exc.retryable else 400
        raise HTTPException(
            status_code=status,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc


@route_router.post("")
async def create_route(
    request: RouteRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Create a route between two resolved places (§26).

    Backend loads lat/lon from DB — client does NOT supply coordinates,
    distance, duration, geometry, or fare.
    """
    await _require_session_access(request.session_id, authorization)
    service = _get_maps_service()

    try:
        route = await service.create_route(
            pickup_place_id=request.pickup_place_id,
            destination_place_id=request.destination_place_id,
        )
        return route.to_api_dict()

    except PlaceNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
    except RouteNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
    except OutOfServiceAreaError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
    except MapsDomainError as exc:
        status = 503 if exc.retryable else 400
        raise HTTPException(
            status_code=status,
            detail={
                "error": exc.code,
                "message": exc.message,
            },
        ) from exc
