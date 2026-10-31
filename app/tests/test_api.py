from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldwatch.api import create_app
from fieldwatch.config import Settings
from fieldwatch.db import connect, init_db

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    conn = connect(tmp_path / "app.sqlite")
    init_db(conn)
    app = create_app(settings, conn=conn, deps={})
    with TestClient(app) as c:
        yield c
    conn.close()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "version" in body


def test_states_lists_all_16(client):
    r = client.get("/api/states")
    assert r.status_code == 200
    assert len(r.json()["states"]) == 16


def test_create_and_list_field(client):
    r = client.post("/api/fields", json={"name": "Test", "geometry": SQUARE})
    assert r.status_code == 201
    field_id = r.json()["id"]
    assert client.get(f"/api/fields/{field_id}").json()["name"] == "Test"
    assert len(client.get("/api/fields").json()["fields"]) == 1


def test_reject_invalid_polygon(client):
    r = client.post(
        "/api/fields",
        json={"name": "Bad", "geometry": {"type": "Point", "coordinates": [1, 2]}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


def test_unknown_field_404(client):
    r = client.get("/api/fields/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_demand_unavailable_without_run(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.get(f"/api/fields/{field_id}/demand")
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"


def test_frames_empty_before_run(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.get(f"/api/fields/{field_id}/frames")
    assert r.status_code == 200
    assert r.json()["frames"] == []


def test_resolve_without_parcels_returns_not_found(client):
    r = client.get("/api/resolve", params={"lat": 51.0, "lon": 7.0})
    assert r.status_code == 200
    assert r.json()["found"] is False


def test_refresh_without_runner_is_503(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.post(f"/api/fields/{field_id}/refresh")
    assert r.status_code == 503


def test_factory_exposes_full_deps(monkeypatch, tmp_path):
    from fieldwatch.api import app_factory

    monkeypatch.setenv("FIELDWATCH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FIELDWATCH_SCHEDULER", "0")
    app = app_factory()
    with TestClient(app) as c:
        assert c.get("/api/config").json()["basemap"] in {"local", "osm"}
        assert c.get("/healthz").status_code == 200


def test_refresh_runs_in_background(tmp_path):
    import threading
    import time

    from fieldwatch.api import create_app
    from fieldwatch.config import Settings
    from fieldwatch.db import connect, init_db

    settings = Settings(data_dir=tmp_path)
    conn = connect(tmp_path / "bg.sqlite")
    init_db(conn)
    done = threading.Event()

    def analyse(field_id):
        time.sleep(0.05)
        done.set()
        return {"ok": True}

    app = create_app(settings, conn=conn, deps={"analyse": analyse})
    with TestClient(app) as c:
        fid = c.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
        r = c.post(f"/api/fields/{fid}/refresh")
        assert r.status_code == 202
        assert r.json()["status"] in {"started", "running"}
        assert done.wait(2)
        st = c.get(f"/api/fields/{fid}/status").json()
        assert st["running"] is False
        assert st["error"] is None
    conn.close()
