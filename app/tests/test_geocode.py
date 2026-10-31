import pytest

from fieldwatch.geocode import Place, search

PAYLOAD = {
    "features": [
        {
            "geometry": {"type": "Point", "coordinates": [7.01, 51.02]},
            "properties": {"name": "Koeln", "city": "Koeln", "postcode": "50667"},
        }
    ]
}


def test_search_returns_place():
    seen = {}

    def fake_fetch(url, params=None, timeout=20.0):
        seen["url"] = url
        seen["params"] = params
        return PAYLOAD

    hit = search("50667", fetch=fake_fetch)
    assert isinstance(hit, Place)
    assert hit.lon == pytest.approx(7.01)
    assert hit.lat == pytest.approx(51.02)
    assert "50667" in hit.label
    assert "photon" in seen["url"]
    assert seen["params"]["q"] == "50667"


def test_empty_query_is_none():
    assert search("   ", fetch=lambda *a, **k: PAYLOAD) is None


def test_no_features_is_none():
    assert search("nirgendwo", fetch=lambda *a, **k: {"features": []}) is None
