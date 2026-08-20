from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Coordinates(BaseModel):
    model_config = ConfigDict(extra='ignore')
    lat: float = Field(ge=-90.0, le=90.0, description='Latitude in degrees (-90 to 90)')
    lon: float = Field(ge=-180.0, le=180.0, description='Longitude in degrees (-180 to 180)')


class AddressDetails(BaseModel):
    model_config = ConfigDict(extra='ignore')
    road: str | None = None
    ward: str | None = None
    district: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = 'Việt Nam'


class LocationResult(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    name: str = ''
    display_name: str
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    latitude: float | None = None
    longitude: float | None = None
    address: AddressDetails | dict[str, Any] | None = None
    formatted_address: str = ''
    place_id: str | None = None
    provider_place_id: str | None = None
    types: list[str] = Field(default_factory=list)
    serviceable: bool | None = None
    provider: str = 'nominatim'


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    query: str
    status: str = 'RESOLVED'
    results: list[LocationResult] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ReverseGeocodeResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    latitude: float
    longitude: float
    lat: float | None = None
    lon: float | None = None
    status: str = 'RESOLVED'
    results: list[LocationResult] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class RouteCoordinates(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    pickup: RouteCoordinates | None = None
    destination: RouteCoordinates | None = None
    pickup_place_id: str | None = None
    destination_place_id: str | None = None
    session_id: str | None = None
    profile: str = 'driving'


class GeoJSONGeometry(BaseModel):
    model_config = ConfigDict(extra='ignore')
    type: str = 'LineString'
    coordinates: list[list[float]] = Field(default_factory=list)


class RouteResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    route_id: str
    distance_m: float
    distance_km: float
    duration_s: float
    duration_minutes: int
    distance_meters: float | None = None
    duration_seconds: float | None = None
    geometry: GeoJSONGeometry | dict[str, Any] | None = None
    legs: list[dict[str, Any]] = Field(default_factory=list)
    provider: str = 'osrm'
    traffic_status: str = 'NONE'
    created_at: str | None = None
    expires_at: str | None = None


class ResolveTripRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    pickup: str | Coordinates = Field(description='Pickup place query or coordinates')
    destination: str | Coordinates = Field(description='Destination place query or coordinates')
    city: str = Field(default='Hà Nội', description='City context for search bias')
    session_id: str | None = None


class ResolveTripResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    pickup: LocationResult
    destination: LocationResult
    route: RouteResponse
