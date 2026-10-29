from __future__ import annotations

import math

from pyproj import Geod
from shapely.geometry import Point, Polygon, shape

_GEOD = Geod(ellps="WGS84")


def _as_shapes(geometry: dict):
    kind = geometry.get("type")
    if kind == "Polygon":
        return [geometry]
    if kind == "MultiPolygon":
        return [{"type": "Polygon", "coordinates": c} for c in geometry["coordinates"]]
    raise ValueError(f"Erwartet Polygon oder MultiPolygon, war {kind!r}")


def validate_polygon(geometry: dict) -> None:
    if not isinstance(geometry, dict):
        raise ValueError("Geometrie muss ein GeoJSON-Objekt sein")
    shapes = _as_shapes(geometry)
    if not shapes:
        raise ValueError("Polygon enthält keine Ringe")
    for poly in shapes:
        rings = poly["coordinates"]
        if not rings:
            raise ValueError("Polygon enthält einen leeren Ring")
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("Ring braucht mindestens 4 Punkte und muss geschlossen sein")
            if list(ring[0]) != list(ring[-1]):
                raise ValueError("Ring muss geschlossen sein (erster == letzter Punkt)")
    if not shape(geometry).is_valid:
        raise ValueError("Polygon ist selbstüberschneidend oder ungültig")


def bbox_of(geometry: dict) -> tuple[float, float, float, float]:
    shapes = [shape(p) for p in _as_shapes(geometry)]
    return (
        min(s.bounds[0] for s in shapes),
        min(s.bounds[1] for s in shapes),
        max(s.bounds[2] for s in shapes),
        max(s.bounds[3] for s in shapes),
    )


def area_m2(geometry: dict) -> float:
    total = 0.0
    for poly in _as_shapes(geometry):
        rings = poly["coordinates"]
        exterior = abs(_GEOD.geometry_area_perimeter(Polygon(rings[0]))[0])
        holes = sum(
            abs(_GEOD.geometry_area_perimeter(Polygon(ring))[0]) for ring in rings[1:]
        )
        total += exterior - holes
    return total


def centroid(geometry: dict) -> tuple[float, float]:
    c = shape(geometry).centroid
    return c.x, c.y


def buffer_bbox(bbox: tuple[float, float, float, float], pct: float = 0.10):
    lon_min, lat_min, lon_max, lat_max = bbox
    dx = (lon_max - lon_min) * pct
    dy = (lat_max - lat_min) * pct
    return (lon_min - dx, lat_min - dy, lon_max + dx, lat_max + dy)


def square_around(lon: float, lat: float, radius_m: float) -> dict:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    ring = [
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    return shape(geometry).contains(Point(lon, lat))
