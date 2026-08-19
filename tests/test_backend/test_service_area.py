"""Unit tests for ServiceAreaChecker — point inside, outside, no config (§38)."""

from __future__ import annotations

import json
import os
import tempfile


from src.backend.maps.service_area import ServiceAreaChecker, _point_in_ring


class TestPointInRing:
    def test_inside_square(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        assert _point_in_ring(5, 5, ring) is True

    def test_outside_square(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        assert _point_in_ring(15, 5, ring) is False

    def test_on_edge(self):
        ring = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        # Edge cases may vary; the important thing is no crash
        _point_in_ring(0, 5, ring)


class TestServiceAreaChecker:
    def _write_geojson(self, geometry: dict) -> str:
        fd, path = tempfile.mkstemp(suffix=".geojson")
        with os.fdopen(fd, "w") as f:
            json.dump(geometry, f)
        return path

    def test_not_configured_fail_open(self):
        """When no polygon loaded, should fail-open (serviceable=True)."""
        checker = ServiceAreaChecker()
        assert checker.configured is False
        result = checker.check(21.0, 105.8)
        assert result.serviceable is True
        assert result.reason == "SERVICE_AREA_NOT_CONFIGURED"

    def test_point_inside_polygon(self):
        # Simple square around Hanoi (approx)
        geojson = {
            "type": "Polygon",
            "coordinates": [[[105.7, 20.9], [106.0, 20.9], [106.0, 21.1], [105.7, 21.1], [105.7, 20.9]]]
        }
        path = self._write_geojson(geojson)
        try:
            checker = ServiceAreaChecker(geojson_path=path, service_area_id="test_hanoi")
            assert checker.configured is True
            result = checker.check(21.0, 105.85)
            assert result.serviceable is True
            assert result.service_area_id == "test_hanoi"
        finally:
            os.unlink(path)

    def test_point_outside_polygon(self):
        geojson = {
            "type": "Polygon",
            "coordinates": [[[105.7, 20.9], [106.0, 20.9], [106.0, 21.1], [105.7, 21.1], [105.7, 20.9]]]
        }
        path = self._write_geojson(geojson)
        try:
            checker = ServiceAreaChecker(geojson_path=path, service_area_id="test_hanoi")
            result = checker.check(10.0, 106.0)  # HCM coordinates — outside Hanoi
            assert result.serviceable is False
            assert result.reason == "OUTSIDE_SERVICE_AREA"
        finally:
            os.unlink(path)

    def test_feature_wrapper(self):
        """Supports GeoJSON Feature (not just raw Geometry)."""
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[105.7, 20.9], [106.0, 20.9], [106.0, 21.1], [105.7, 21.1], [105.7, 20.9]]]
            }
        }
        path = self._write_geojson(geojson)
        try:
            checker = ServiceAreaChecker(geojson_path=path, service_area_id="test")
            assert checker.configured is True
        finally:
            os.unlink(path)

    def test_multipolygon(self):
        geojson = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[105.7, 20.9], [106.0, 20.9], [106.0, 21.1], [105.7, 21.1], [105.7, 20.9]]],
                [[[106.5, 10.5], [106.9, 10.5], [106.9, 10.9], [106.5, 10.9], [106.5, 10.5]]],
            ]
        }
        path = self._write_geojson(geojson)
        try:
            checker = ServiceAreaChecker(geojson_path=path, service_area_id="multi")
            # Hanoi point
            assert checker.check(21.0, 105.85).serviceable is True
            # HCM point
            assert checker.check(10.7, 106.7).serviceable is True
            # Neither
            assert checker.check(15.0, 108.0).serviceable is False
        finally:
            os.unlink(path)

    def test_invalid_path(self):
        checker = ServiceAreaChecker(geojson_path="/nonexistent/path.geojson")
        assert checker.configured is False

    def test_unsupported_geometry(self):
        geojson = {"type": "Point", "coordinates": [105.8, 21.0]}
        path = self._write_geojson(geojson)
        try:
            checker = ServiceAreaChecker(geojson_path=path)
            assert checker.configured is False
        finally:
            os.unlink(path)
