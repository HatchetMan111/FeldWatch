from datetime import date

import numpy as np
import pytest

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.cli import run_point
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

GRID = make_grid((6.99, 50.99, 7.02, 51.02))


def _runtime():
    shape = (GRID.height, GRID.width)
    return {
        "search": lambda geometry, months, max_cloud: [
            SceneRef("a", "2026-10-01T10:00:00Z", 0.0, {"red": "r", "nir": "n", "scl": "s"})
        ],
        "grid": lambda geometry: GRID,
        "arrays": lambda scene, geometry, grid: SceneArrays(
            red=np.full(shape, 0.1, dtype=np.float32),
            nir=np.full(shape, 0.4, dtype=np.float32),
            scl=np.full(shape, 4, dtype=np.float32),
        ),
        "forecast": lambda lat, lon, days: [DailyEto(f"2026-10-{20+i:02d}", 2.0, 0.0) for i in range(days)],
    }


def test_run_point_returns_series_and_demand():
    out = run_point(51.0, 7.0, 100.0, runtime=_runtime(), today=date(2026, 10, 20))
    assert out["geometry"]["type"] == "Polygon"
    assert len(out["observations"]) == 1
    assert out["demand"]["status"] == "ok"
    assert out["demand"]["week_mm"] > 0
    assert "frame" not in out["observations"][0]


def test_run_point_empty_search_degrades():
    runtime = _runtime()
    runtime["search"] = lambda geometry, months, max_cloud: []
    out = run_point(51.0, 7.0, 100.0, runtime=runtime, today=date(2026, 10, 20))
    assert out["observations"] == []
    assert out["demand"]["status"] == "unavailable"


def test_main_requires_lat_lon(capsys):
    from fieldwatch.cli import main

    code = main(["run"])
    assert code == 2
    assert "lat" in capsys.readouterr().err.lower()
