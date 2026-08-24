"""Authenticated & Public-ready Maps API; provides standardized OSM geocoding and routing."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from src.backend.api.routes.sessions import _require_session_access
from src.backend.maps.contracts import (
    MapsDomainError,
    PlaceCandidateExpiredError,
    PlaceNotFoundError,
    validate_latitude,
    validate_longitude,
)
from src.backend.services.maps_service import MapsService

router = APIRouter(prefix="/places", tags=["maps"])
route_router = APIRouter(prefix="/routes", tags=["maps"])
maps_router = APIRouter(prefix="/maps", tags=["maps"])

_maps_service: MapsService | None = None


def _get_maps_service() -> MapsService:
    global _maps_service
    if _maps_service is None:
        _maps_service = MapsService()
    return _maps_service


class PlaceResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=30)
    provider_place_id: str = Field(min_length=1, max_length=255)
    session_id: str = Field(min_length=1, max_length=64)


class RouteCoordinatesDTO(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class RouteRequestDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pickup: RouteCoordinatesDTO | None = None
    destination: RouteCoordinatesDTO | None = None
    pickup_place_id: str | None = Field(default=None, max_length=32)
    destination_place_id: str | None = Field(default=None, max_length=32)
    session_id: str | None = Field(default=None, max_length=64)
    profile: str = "driving"


class ResolveTripRequestDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pickup: Any = Field(description="Pickup location query or coordinates dict")
    destination: Any = Field(description="Destination location query or coordinates dict")
    city: str = Field(default="Hà Nội", max_length=100)
    session_id: str | None = Field(default=None, max_length=64)


def _http_error(exc: MapsDomainError) -> HTTPException:
    if isinstance(exc, (PlaceNotFoundError, PlaceCandidateExpiredError)):
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code in {"OUT_OF_SERVICE_AREA", "ROUTE_NOT_FOUND"}:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": exc.code, "message": exc.message}},
    )


# ---------------------------------------------------------------------------
# Standard /maps Endpoints
# ---------------------------------------------------------------------------


@maps_router.get("/search")
async def maps_search(
    q: str = Query(min_length=1, max_length=500),
    city: str | None = Query(default=None, max_length=100),
    session_id: str = Query(default="", max_length=64),
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Search for locations using Nominatim with Vietnamese normalization and city context."""
    if session_id:
        await _require_session_access(session_id, authorization)
    return await _get_maps_service().search_places(q, session_id=session_id, limit=limit, city=city)


@maps_router.get("/reverse")
async def maps_reverse(
    lat: float = Query(ge=-90.0, le=90.0),
    lon: float = Query(ge=-180.0, le=180.0),
    session_id: str = Query(default="", max_length=64),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Reverse geocode coordinates into a structured address."""
    if session_id:
        await _require_session_access(session_id, authorization)
    return await _get_maps_service().reverse_geocode(lat, lon, session_id=session_id)


@maps_router.post("/route")
async def maps_route(
    request: RouteRequestDTO,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Calculate driving route between pickup and destination coordinates or place IDs."""
    if request.session_id:
        await _require_session_access(request.session_id, authorization)
    try:
        if request.pickup is not None and request.destination is not None:
            route = await _get_maps_service().create_route_coordinates(
                pickup_lat=request.pickup.lat,
                pickup_lon=request.pickup.lon,
                dest_lat=request.destination.lat,
                dest_lon=request.destination.lon,
                profile=request.profile,
            )
            return route.to_api_dict()
        if request.pickup_place_id and request.destination_place_id:
            route = await _get_maps_service().create_route(
                pickup_place_id=request.pickup_place_id,
                destination_place_id=request.destination_place_id,
            )
            return route.to_api_dict()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INPUT", "message": "Either (pickup, destination) coordinates or place IDs are required."}},
        )
    except MapsDomainError as exc:
        raise _http_error(exc) from exc


@maps_router.post("/resolve-trip")
async def maps_resolve_trip(
    request: ResolveTripRequestDTO,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Resolve pickup & destination queries to coordinates and calculate road route in a single call."""
    if request.session_id:
        await _require_session_access(request.session_id, authorization)
    try:
        return await _get_maps_service().resolve_trip(
            pickup=request.pickup,
            destination=request.destination,
            city=request.city,
            session_id=request.session_id or "",
        )
    except MapsDomainError as exc:
        raise _http_error(exc) from exc


@maps_router.get("/health")
async def maps_health() -> dict[str, Any]:
    """Check Map subsystem status and provider configurations."""
    return await _get_maps_service().health_check()


# ---------------------------------------------------------------------------
# Backward-Compatible /places and /routes Endpoints
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_places(
    q: str = Query(min_length=1, max_length=500),
    session_id: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    await _require_session_access(session_id, authorization)
    return await _get_maps_service().search_places(q, session_id=session_id, limit=limit)


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    session_id: str = Query(min_length=1, max_length=64),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    await _require_session_access(session_id, authorization)
    return await _get_maps_service().reverse_geocode(lat, lon, session_id=session_id)


@router.post("/resolve")
async def resolve_place(
    request: PlaceResolveRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    await _require_session_access(request.session_id, authorization)
    try:
        place = await _get_maps_service().resolve_place(
            provider=request.provider,
            provider_place_id=request.provider_place_id,
            session_id=request.session_id,
        )
        return place.to_api_dict()
    except MapsDomainError as exc:
        raise _http_error(exc) from exc


@route_router.post("")
async def create_route(request: RouteRequestDTO, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if request.session_id:
        await _require_session_access(request.session_id, authorization)
    try:
        if request.pickup is not None and request.destination is not None:
            route = await _get_maps_service().create_route_coordinates(
                pickup_lat=request.pickup.lat,
                pickup_lon=request.pickup.lon,
                dest_lat=request.destination.lat,
                dest_lon=request.destination.lon,
                profile=request.profile,
            )
            return route.to_api_dict()
        if request.pickup_place_id and request.destination_place_id:
            route = await _get_maps_service().create_route(
                pickup_place_id=request.pickup_place_id,
                destination_place_id=request.destination_place_id,
            )
            return route.to_api_dict()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_INPUT", "message": "Either (pickup, destination) coordinates or place IDs required."},
        )
    except MapsDomainError as exc:
        raise _http_error(exc) from exc
