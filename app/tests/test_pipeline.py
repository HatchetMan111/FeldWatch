from datetime import date

import numpy as np
import pytest
from affine import Affine

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.pipeline import analyse_field
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}
GRID = make_grid((6.99, 50.99, 7.02, 51.02))


def _arrays(red=0.1, nir=0.5, scl=4):
    shape = (GRID.height, GRID.width)
    return SceneArrays(
        red=np.full(shape, red, dtype=np.float32),
        nir=np.full(shape, nir, dtype=np.float32),
        scl=np.full(shape, scl, dtype=np.float32),
    )


def _scene(day: str) -> SceneRef:
    return SceneRef(
        id=day,
        datetime=f"{day}T10:00:00Z",
        cloud_cover=0.0,
        hrefs={"red": "r", "nir": "n", "scl": "s"},
    )


def _forecast(n=7, value=2.0):
    return [DailyEto(f"2026-10-{20+i:02d}", value, 0.0) for i in range(n)]


def test_analyse_field_produces_observations_and_demand():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-09-01"), _scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert len(result.observations) == 2
    assert result.observations[0]["median_ndvi"] == pytest.approx(2 / 3, abs=1e-3)
    assert result.demand["week_mm"] > 0
    assert result.demand["complete"] is True
    assert "insufficient_pixels" not in result.flags


def test_all_cloudy_scene_is_skipped_with_flag():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(scl=8),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert result.observations == []
    assert "no_clear_observation" in result.flags
    assert result.demand["status"] == "unavailable"


def test_tiny_field_is_flagged():
    tiny = {
        "type": "Polygon",
        "coordinates": [[[7.0, 51.0], [7.00002, 51.0], [7.00002, 51.00002], [7.0, 51.00002], [7.0, 51.0]]],
    }
    result = analyse_field(
        tiny,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert "insufficient_pixels" in result.flags


def test_stale_canopy_flagged():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-06-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert "stale_canopy" in result.flags


def test_missing_forecast_degrades():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=[DailyEto("2026-10-20", None, None)],
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert result.demand["complete"] is False
    assert result.demand["status"] == "unavailable"


def test_progress_is_reported_per_scene():
    seen = []
    analyse_field(
        SQUARE,
        scenes=[_scene("2026-09-01"), _scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
        progress=lambda done, total: seen.append((done, total)),
    )
    assert seen[-1] == (2, 2)


def test_parallel_reads_keep_results():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-09-01"), _scene("2026-10-01"), _scene("2026-10-10")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
        workers=3,
    )
    assert len(result.observations) == 3
