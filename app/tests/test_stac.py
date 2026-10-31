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

    def fake_fetch(url, body=None, timeout=20.0):
        seen["url"] = url
        seen["body"] = body
        return PAYLOAD

    search(SQUARE, months=6, max_cloud=50, fetch=fake_fetch)
    assert "earth-search" in seen["url"]
    assert seen["body"]["collections"] == ["sentinel-2-l2a"]
    assert seen["body"]["query"]["eo:cloud_cover"]["lt"] == 50
    assert seen["body"]["intersects"]["type"] == "Polygon"
    assert seen["body"]["datetime"].endswith("Z/..")


def test_search_empty_collection():
    assert search(SQUARE, fetch=lambda *a, **k: {"features": []}) == []


def test_search_missing_features_raises():
    with pytest.raises(ValueError, match="features"):
        search(SQUARE, fetch=lambda *a, **k: {})


def _feature(day: str, cloud: float, idx: int) -> dict:
    return {
        "id": f"s{idx}",
        "properties": {"datetime": f"{day}T10:00:00Z", "eo:cloud_cover": cloud},
        "assets": {
            "red": {"href": "r"},
            "nir": {"href": "n"},
            "scl": {"href": "s"},
        },
    }


def test_search_dedupes_dates_and_thins():
    days = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]
    features = []
    for i, day in enumerate(days):
        features.append(_feature(day, 50.0, i * 2))
        features.append(_feature(day, 5.0, i * 2 + 1))
    scenes = search(SQUARE, fetch=lambda *a, **k: {"features": features}, max_scenes=2)
    assert len(scenes) == 2
    assert len({s.datetime[:10] for s in scenes}) == 2
    assert all(s.cloud_cover == 5.0 for s in scenes)
