import pytest

from fieldwatch.db import (
    connect,
    create_field,
    delete_field,
    get_demand,
    get_field,
    get_observations,
    init_db,
    list_fields,
    log_source,
    overview_fields,
    save_demand,
    save_observations,
    update_field_name,
)

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "test.sqlite")
    init_db(connection)
    yield connection
    connection.close()


def test_create_and_get(conn):
    field_id = create_field(conn, "Acker Nord", SQUARE, 800_000.0, "NW")
    row = get_field(conn, field_id)
    assert row["name"] == "Acker Nord"
    assert row["area_m2"] == pytest.approx(800_000.0)
    assert row["geometry"]["type"] == "Polygon"


def test_list_and_delete(conn):
    first = create_field(conn, "A", SQUARE, 1.0, "NW")
    create_field(conn, "B", SQUARE, 2.0, "BY")
    assert [f["name"] for f in list_fields(conn)] == ["A", "B"]
    assert delete_field(conn, first) is True
    assert delete_field(conn, 9999) is False
    assert len(list_fields(conn)) == 1


def test_observations_replace(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    save_observations(conn, field_id, [
        {"date": "2026-01-01", "median_ndvi": 0.2, "mean_ndvi": 0.21,
         "clear_pct": 0.9, "pixels": 100, "frame": b"\x01\x02"},
    ])
    save_observations(conn, field_id, [
        {"date": "2026-02-01", "median_ndvi": 0.4, "mean_ndvi": 0.41,
         "clear_pct": 0.8, "pixels": 100, "frame": b"\x03"},
    ])
    rows = get_observations(conn, field_id)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-02-01"
    assert rows[0]["frame"] == b"\x03"


def test_demand_roundtrip(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    save_demand(conn, field_id, {"week_mm": 4.2, "week_m3": 3360.0, "stale_canopy": False})
    payload = get_demand(conn, field_id)
    assert payload["week_mm"] == pytest.approx(4.2)
    assert payload["stale_canopy"] is False


def test_source_log(conn):
    log_source(conn, "stac", "https://example", 200, 1234, 50, "Copernicus")
    assert conn.execute("SELECT COUNT(*) FROM source_log").fetchone()[0] == 1


def test_wal_mode(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_rename_field(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    assert update_field_name(conn, field_id, "Acker West") is True
    assert get_field(conn, field_id)["name"] == "Acker West"
    assert update_field_name(conn, 9999, "X") is False


def test_list_fields_reports_analysis_state(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    assert list_fields(conn)[0]["last_obs"] is None
    assert list_fields(conn)[0]["obs_count"] == 0
    save_observations(conn, field_id, [
        {"date": "2026-01-01", "median_ndvi": 0.2, "mean_ndvi": 0.21,
         "clear_pct": 0.9, "pixels": 100},
        {"date": "2026-02-01", "median_ndvi": 0.4, "mean_ndvi": 0.41,
         "clear_pct": 0.8, "pixels": 100},
    ])
    row = list_fields(conn)[0]
    assert row["last_obs"] == "2026-02-01"
    assert row["obs_count"] == 2
    assert row["geometry"]["type"] == "Polygon"


def test_overview_fields_empty(conn):
    assert overview_fields(conn) == []


def test_overview_fields_joins_last_obs_and_demand(conn):
    field_id = create_field(conn, "Acker Nord", SQUARE, 800_000.0, "NW")
    save_observations(conn, field_id, [
        {"date": "2026-06-10", "median_ndvi": 0.40, "clear_pct": 0.9, "pixels": 100},
        {"date": "2026-07-01", "median_ndvi": 0.62, "clear_pct": 0.9, "pixels": 100},
    ])
    save_demand(conn, field_id, {
        "status": "ok", "week_mm": 25.8, "balance_mm": -2.3,
        "cover": 0.6, "canopy_date": "2026-07-01", "canopy_age_days": 10,
        "kcb": 0.82, "missing_days": 0,
    })
    rows = overview_fields(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["last_obs"] == "2026-07-01"
    assert row["last_ndvi"] == pytest.approx(0.62)
    assert row["obs_count"] == 2
    assert row["demand"]["week_mm"] == pytest.approx(25.8)
    assert row["demand"]["balance_mm"] == pytest.approx(-2.3)
    assert row["demand"]["canopy_age_days"] == 10
    # Feldgeometrie bleibt ueber _field_row geparst
    assert row["geometry"]["type"] == "Polygon"


def test_overview_fields_unanalysed_has_none(conn):
    create_field(conn, "Leer", SQUARE, 100_000.0, "none")
    rows = overview_fields(conn)
    assert rows[0]["last_obs"] is None
    assert rows[0]["last_ndvi"] is None
    assert rows[0]["obs_count"] == 0
    assert rows[0]["demand"] is None
