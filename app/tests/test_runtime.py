from datetime import date

import numpy as np
import pytest

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.config import Settings
from fieldwatch.db import connect, create_field, get_demand, get_observations, init_db
from fieldwatch.runtime import analyse_field_by_id
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}
GRID = make_grid((6.99, 50.99, 7.02, 51.02))


class FakeCache:
    def get(self, key):
        return None

    def put(self, key, value):
        pass


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "db.sqlite")
    init_db(connection)
    yield connection
    connection.close()


def _clients():
    shape = (GRID.height, GRID.width)
    return {
        "search": lambda geometry, months, max_cloud: [
            SceneRef("s1", "2026-10-01T10:00:00Z", 0.0, {"red": "r", "nir": "n", "scl": "s"})
        ],
        "grid": lambda geometry: GRID,
        "arrays": lambda scene, geometry, grid: SceneArrays(
            red=np.full(shape, 0.1, dtype=np.float32),
            nir=np.full(shape, 0.5, dtype=np.float32),
            scl=np.full(shape, 4, dtype=np.float32),
        ),
        "forecast": lambda lat, lon, days: [DailyEto(f"2026-10-{20+i:02d}", 2.0, 0.0) for i in range(days)],
    }


def test_analyse_field_by_id_persists(conn, tmp_path):
    settings = Settings(data_dir=tmp_path)
    field_id = create_field(conn, "A", SQUARE, 800_000.0, "NW")
    result = analyse_field_by_id(
        field_id, settings=settings, conn=conn, cache=FakeCache(),
        clients=_clients(), today=date(2026, 10, 20)
    )
    assert result["demand"]["status"] == "ok"
    assert len(get_observations(conn, field_id)) == 1
    assert get_demand(conn, field_id)["week_mm"] > 0


def test_analyse_unknown_field_raises(conn, tmp_path):
    settings = Settings(data_dir=tmp_path)
    with pytest.raises(KeyError):
        analyse_field_by_id(999, settings=settings, conn=conn, cache=FakeCache(), clients=_clients())


def test_progress_is_recorded(conn, tmp_path):
    from fieldwatch.runtime import PROGRESS

    settings = Settings(data_dir=tmp_path)
    field_id = create_field(conn, "A", SQUARE, 800_000.0, "NW")
    analyse_field_by_id(
        field_id, settings=settings, conn=conn, cache=FakeCache(),
        clients=_clients(), today=date(2026, 10, 20)
    )
    assert PROGRESS[field_id]["done"] == 1
    assert PROGRESS[field_id]["total"] == 1


def test_refresh_demand_updates_forecast_without_scenes(conn, tmp_path):
    from fieldwatch.db import get_demand
    from fieldwatch.runtime import refresh_demand_by_id

    settings = Settings(data_dir=tmp_path)
    field_id = create_field(conn, "A", SQUARE, 800_000.0, "NW")
    analyse_field_by_id(
        field_id, settings=settings, conn=conn, cache=FakeCache(),
        clients=_clients(), today=date(2026, 10, 20)
    )

    calls = []

    def wet_forecast(lat, lon, days):
        calls.append((lat, lon, days))
        return [DailyEto(f"2026-10-{20+i:02d}", 6.0, 0.0) for i in range(days)]

    result = refresh_demand_by_id(
        field_id, settings=settings, conn=conn,
        clients={"forecast": wet_forecast},
    )
    assert len(calls) == 1
    assert calls[0][0] == pytest.approx(51.005)
    assert calls[0][1] == pytest.approx(7.005)
    assert calls[0][2] == 7
    payload = get_demand(conn, field_id)
    assert payload["week_mm"] == pytest.approx(payload["kcb"] * 6.0 * 7, rel=1e-3)
    assert result["canopy_date"] == "2026-10-01"


def test_refresh_demand_skips_unanalysed_field(conn, tmp_path):
    from fieldwatch.runtime import refresh_demand_by_id

    settings = Settings(data_dir=tmp_path)
    field_id = create_field(conn, "A", SQUARE, 800_000.0, "NW")
    result = refresh_demand_by_id(field_id, settings=settings, conn=conn)
    assert result["status"] == "skipped"


def test_refresh_demand_unknown_field_raises(conn, tmp_path):
    from fieldwatch.runtime import refresh_demand_by_id

    settings = Settings(data_dir=tmp_path)
    with pytest.raises(KeyError):
        refresh_demand_by_id(999, settings=settings, conn=conn)


def test_cache_key_includes_grid_origin(tmp_path):
    from fieldwatch.runtime import CACHE_KEY

    grid_a = make_grid((6.99, 50.99, 7.02, 51.02))
    shifted = make_grid((7.99, 50.99, 8.02, 51.02))
    key_a = CACHE_KEY.format(
        scene_id="s1", asset="rgb", grid_crs=grid_a.crs,
        grid_x0=grid_a.transform.c, grid_y0=grid_a.transform.f,
        grid_w=grid_a.width, grid_h=grid_a.height,
    )
    key_b = CACHE_KEY.format(
        scene_id="s1", asset="rgb", grid_crs=shifted.crs,
        grid_x0=shifted.transform.c, grid_y0=shifted.transform.f,
        grid_w=shifted.width, grid_h=shifted.height,
    )
    assert key_a != key_b
