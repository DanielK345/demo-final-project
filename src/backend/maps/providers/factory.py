"""Provider factory — instantiate the configured geocoding/routing providers.

Reads from ``Settings`` to determine which provider implementation to use and
returns a configured instance. Future providers are added here.
"""

from __future__ import annotations

from src.backend.config import Settings, get_settings
from src.backend.maps.providers.base import GeocodingProvider, RoutingProvider
from src.backend.maps.providers.nominatim import NominatimProvider
from src.backend.maps.providers.osrm import OSRMProvider


def get_geocoding_provider(settings: Settings | None = None) -> GeocodingProvider:
    """Return the configured geocoding provider instance."""
    s = settings or get_settings()
    provider_name = s.geocoding_provider.lower()

    if provider_name == "nominatim":
        return NominatimProvider(
            base_url=s.nominatim_base_url,
            timeout=s.map_request_timeout_seconds,
            country_code=s.map_country_code,
        )

    # Future: GoongProvider, VietMapProvider, GoogleProvider, MapboxProvider
    raise ValueError(f"Unknown geocoding provider: {provider_name}")


def get_routing_provider(settings: Settings | None = None) -> RoutingProvider:
    """Return the configured routing provider instance."""
    s = settings or get_settings()
    provider_name = s.routing_provider.lower()

    if provider_name == "osrm":
        return OSRMProvider(
            base_url=s.osrm_base_url,
            timeout=s.map_request_timeout_seconds,
            source_data_version=s.osm_data_version,
        )

    # Future: GoongProvider, VietMapProvider, GoogleProvider, MapboxProvider
    raise ValueError(f"Unknown routing provider: {provider_name}")
