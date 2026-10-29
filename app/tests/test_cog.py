from pathlib import Path

import numpy as np
import pytest
import rasterio

from fieldwatch.cog import CogCache, Grid, make_grid, read_scene
from fieldwatch.stac import SceneRef

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


def test_make_grid_produces_10m_pixels():
    grid = make_grid((7.0, 51.0, 7.01, 51.01), res_m=10.0)
    assert grid.crs.startswith("EPSG:32")
    assert grid.width > 50
    assert grid.height > 50
    assert 8.0 < abs(grid.transform.a) < 12.0


def test_make_grid_caps_size():
    grid = make_grid((6.0, 50.0, 8.0, 52.0), res_m=10.0, max_px=256)
    assert grid.width <= 256
    assert grid.height <= 256
    assert grid.width >= 1 and grid.height >= 1


def test_make_grid_at_zone_border_does_not_collapse():
    grid = make_grid((5.99, 51.0, 6.01, 51.002), res_m=10.0)
    assert grid.width >= 1
    assert grid.height >= 1
    assert np.isfinite(grid.transform.a)
    assert abs(grid.transform.a) > 0


def _write_tif(path: Path, value: int, grid) -> Path:
    data = np.full((grid.height, grid.width), value, dtype=np.uint16)
    with rasterio.open(
        path, "w", driver="GTiff", width=grid.width, height=grid.height, count=1,
        dtype="uint16", crs=grid.crs, transform=grid.transform,
    ) as dst:
        dst.write(data, 1)
    return path


def test_read_scene_reprojects_into_grid(tmp_path):
    grid = make_grid((7.0, 51.0, 7.01, 51.01))
    red = _write_tif(tmp_path / "red.tif", 100, grid)
    nir = _write_tif(tmp_path / "nir.tif", 500, grid)
    scl = _write_tif(tmp_path / "scl.tif", 4, grid)
    scene = SceneRef(
        id="x", datetime="2026-10-01T10:00:00Z", cloud_cover=0.0,
        hrefs={"red": str(red), "nir": str(nir), "scl": str(scl)},
    )
    arrays = read_scene(scene, SQUARE, grid)
    assert arrays.red.shape == (grid.height, grid.width)
    assert arrays.scl.shape == (grid.height, grid.width)
    assert float(np.nanmedian(arrays.nir)) == pytest.approx(500, abs=1)


def test_cache_evicts_oldest(tmp_path):
    cache = CogCache(tmp_path, max_bytes=3000)
    cache.put("a", np.zeros((40, 40), dtype=np.float32))
    cache.put("b", np.zeros((40, 40), dtype=np.float32))
    cache.put("c", np.zeros((40, 40), dtype=np.float32))
    assert cache.size() <= 3000
    assert cache.get("a") is None


def test_cache_roundtrip(tmp_path):
    cache = CogCache(tmp_path, max_bytes=10_000_000)
    arr = np.arange(100, dtype=np.float32).reshape(10, 10)
    cache.put("k", arr)
    np.testing.assert_array_equal(cache.get("k"), arr)
