import pytest

from fieldwatch.geo import (
    area_m2,
    bbox_of,
    buffer_bbox,
    centroid,
    point_in_geometry,
    square_around,
    validate_polygon,
)

SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]
    ],
}


def test_bbox():
    assert bbox_of(SQUARE) == pytest.approx((7.0, 51.0, 7.01, 51.01))


def test_area_is_plausible():
    assert 700_000 < area_m2(SQUARE) < 900_000


def test_area_of_polygon_with_hole():
    outer = SQUARE["coordinates"][0]
    hole = [[7.004, 51.004], [7.006, 51.004], [7.006, 51.006], [7.004, 51.006], [7.004, 51.004]]
    geom = {"type": "Polygon", "coordinates": [outer, hole]}
    assert area_m2(geom) < area_m2(SQUARE)


def test_centroid_inside_square():
    lon, lat = centroid(SQUARE)
    assert lon == pytest.approx(7.005, abs=1e-6)
    assert lat == pytest.approx(51.005, abs=1e-6)


def test_validate_rejects_point():
    with pytest.raises(ValueError, match="Polygon"):
        validate_polygon({"type": "Point", "coordinates": [7.0, 51.0]})


def test_validate_rejects_unclosed_ring():
    bad = {"type": "Polygon", "coordinates": [[[7.0, 51.0], [7.1, 51.0], [7.1, 51.1]]]}
    with pytest.raises(ValueError, match="geschlossen"):
        validate_polygon(bad)


def test_validate_accepts_multipolygon():
    validate_polygon({"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]})


def test_buffer_bbox_grows():
    out = buffer_bbox((7.0, 51.0, 7.01, 51.01), 0.1)
    assert out[0] < 7.0 and out[2] > 7.01


def test_square_around_is_valid_and_has_area():
    poly = square_around(7.0, 51.0, 500.0)
    validate_polygon(poly)
    assert area_m2(poly) == pytest.approx(1_000_000, rel=0.15)


def test_point_in_geometry():
    assert point_in_geometry(7.005, 51.005, SQUARE)
    assert not point_in_geometry(7.0, 51.0, SQUARE)
    assert not point_in_geometry(8.0, 51.0, SQUARE)
