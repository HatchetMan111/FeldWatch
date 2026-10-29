import pytest

from fieldwatch.stac import SceneRef, search

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}

PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S2B_old",
            "properties": {"datetime": "2026-01-01T10:00:00Z", "eo:cloud_cover": 12.0},
            "assets": {
                "red": {"href": "https://example/red_old.tif"},
                "nir": {"href": "https://example/nir_old.tif"},
                "scl": {"href": "https://example/scl_old.tif"},
                "visual": {"href": "https://example/visual_old.tif"},
            },
        },
        {
            "id": "S2A_new",
            "properties": {"datetime": "2026-10-01T10:00:00Z", "eo:cloud_cover": 3.0},
            "assets": {
                "red": {"href": "https://example/red_new.tif"},
                "nir": {"href": "https://example/nir_new.tif"},
                "scl": {"href": "https://example/scl_new.tif"},
            },
        },
        {
            "id": "S2A_incomplete",
            "properties": {"datetime": "2026-09-01T10:00:00Z", "eo:cloud_cover": 1.0},
            "assets": {"red": {"href": "https://example/red.tif"}},
        },
    ],
}


def test_search_returns_sorted_and_complete():
    scenes = search(SQUARE, fetch=lambda *a, **k: PAYLOAD)
    assert [s.id for s in scenes] == ["S2A_new", "S2B_old"]
    assert all(isinstance(s, SceneRef) for s in scenes)
    assert scenes[0].hrefs["nir"].endswith("nir_new.tif")


def test_search_request_has_expected_fields():
    seen = {}

    def fake_fetch(url, params=None, timeout=20.0):
        seen["url"] = url
        seen["params"] = params
        return PAYLOAD

    search(SQUARE, months=6, max_cloud=50, fetch=fake_fetch)
    assert "earth-search" in seen["url"]
    assert seen["params"]["collections"] == "sentinel-2-l2a"
    assert seen["params"]["query"]["eo:cloud_cover"]["lt"] == 50
    assert seen["params"]["intersects"]["type"] == "Polygon"
    assert seen["params"]["datetime"].endswith("Z/..")


def test_search_empty_collection():
    assert search(SQUARE, fetch=lambda *a, **k: {"features": []}) == []


def test_search_missing_features_raises():
    with pytest.raises(ValueError, match="features"):
        search(SQUARE, fetch=lambda *a, **k: {})
