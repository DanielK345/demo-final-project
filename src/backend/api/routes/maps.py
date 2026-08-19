"""Authenticated Maps API; clients never call providers or submit trusted coordinates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.backend.api.routes.sessions import _require_session_access
from src.backend.maps.contracts import MapsDomainError, PlaceCandidateExpiredError, PlaceNotFoundError
from src.backend.services.maps_service import MapsService

router = APIRouter(prefix="/places", tags=["maps"])
route_router = APIRouter(prefix="/routes", tags=["maps"])
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


class RouteRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    pickup_place_id: str = Field(min_length=1, max_length=32)
    destination_place_id: str = Field(min_length=1, max_length=32)


def _http_error(exc: MapsDomainError) -> HTTPException:
    if isinstance(exc, (PlaceNotFoundError, PlaceCandidateExpiredError)):
        status_code = 404
    elif exc.code in {"OUT_OF_SERVICE_AREA", "ROUTE_NOT_FOUND"}:
        status_code = 422
    else:
        status_code = 503 if exc.retryable else 400
    return HTTPException(status_code=status_code, detail={"error": exc.code, "message": exc.message})


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
async def create_route(request: RouteRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    await _require_session_access(request.session_id, authorization)
    try:
        route = await _get_maps_service().create_route(
            pickup_place_id=request.pickup_place_id,
            destination_place_id=request.destination_place_id,
        )
        return route.to_api_dict()
    except MapsDomainError as exc:
        raise _http_error(exc) from exc
