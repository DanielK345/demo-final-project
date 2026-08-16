"""Service area checker — determines whether a location is within AloSM's
operational zone.

Supports GeoJSON ``Polygon`` and ``MultiPolygon`` geometries.

EXTERNAL_BLOCKED: The actual service-area polygon must be provided by
Product/Ops. AI does not decide which districts/cities AloSM operates in.
Code and tests are fully implemented; only the GeoJSON data file is missing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ServiceAreaResult:
    """Result of a service-area check."""

    __slots__ = ("serviceable", "service_area_id", "reason")

    def __init__(
        self,
        *,
        serviceable: bool,
        service_area_id: str | None = None,
        reason: str = "",
    ) -> None:
        self.serviceable = serviceable
        self.service_area_id = service_area_id
        self.reason = reason


def _point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon.

    Pure-Python implementation — no heavy geo library dependency required for
    a simple containment check. Uses standard winding-number approach.
    """
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    """Check if (lon, lat) is inside a GeoJSON Polygon (list of rings)."""
    if not polygon:
        return False
    # Must be inside outer ring
    if not _point_in_ring(lon, lat, polygon[0]):
        return False
    # Must NOT be inside any hole
    for hole in polygon[1:]:
        if _point_in_ring(lon, lat, hole):
            return False
    return True


def _point_in_multipolygon(
    lon: float, lat: float, multi: list[list[list[list[float]]]]
) -> bool:
    """Check if (lon, lat) is inside a GeoJSON MultiPolygon."""
    return any(_point_in_polygon(lon, lat, polygon) for polygon in multi)


class ServiceAreaChecker:
    """Checks whether a coordinate falls within the configured service area.

    Parameters
    ----------
    geojson_path:
        Path to a GeoJSON file containing a Polygon or MultiPolygon Feature/Geometry.
    service_area_id:
        Identifier for this service area (e.g. ``hanoi_core``).
    """

    def __init__(
        self,
        geojson_path: str = "",
        service_area_id: str = "",
    ) -> None:
        self._service_area_id = service_area_id
        self._geometry: dict[str, Any] | None = None
        self._loaded = False

        if geojson_path:
            self._load(geojson_path)

    def _load(self, path: str) -> None:
        """Load and validate the GeoJSON file."""
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load service area GeoJSON from %s: %s", path, exc)
            return

        # Accept both a raw Geometry and a Feature
        geometry = raw
        if raw.get("type") == "Feature":
            geometry = raw.get("geometry", {})
        elif raw.get("type") == "FeatureCollection":
            features = raw.get("features", [])
            if features:
                geometry = features[0].get("geometry", {})

        geo_type = geometry.get("type", "")
        if geo_type not in ("Polygon", "MultiPolygon"):
            logger.warning("Service area GeoJSON has unsupported type: %s", geo_type)
            return

        self._geometry = geometry
        self._loaded = True
        logger.info("Service area loaded: type=%s, id=%s", geo_type, self._service_area_id)

    @property
    def configured(self) -> bool:
        """Whether a valid service area polygon has been loaded."""
        return self._loaded and self._geometry is not None

    def check(self, latitude: float, longitude: float) -> ServiceAreaResult:
        """Check if the given coordinates are within the service area.

        Returns ``ServiceAreaResult`` with:
        - ``serviceable=True`` if inside the area
        - ``serviceable=False`` if outside
        - ``serviceable=None`` reason ``NOT_CONFIGURED`` if no polygon loaded
        """
        if not self.configured:
            return ServiceAreaResult(
                serviceable=True,  # fail-open when not configured (§19)
                service_area_id=None,
                reason="SERVICE_AREA_NOT_CONFIGURED",
            )

        assert self._geometry is not None
        geo_type = self._geometry["type"]
        coords = self._geometry["coordinates"]

        if geo_type == "Polygon":
            inside = _point_in_polygon(longitude, latitude, coords)
        else:
            inside = _point_in_multipolygon(longitude, latitude, coords)

        return ServiceAreaResult(
            serviceable=inside,
            service_area_id=self._service_area_id if inside else None,
            reason="" if inside else "OUTSIDE_SERVICE_AREA",
        )
