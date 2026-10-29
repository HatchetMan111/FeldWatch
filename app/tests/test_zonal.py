import numpy as np
import pytest
from affine import Affine

from fieldwatch.zonal import polygon_mask, zonal_stats


def test_polygon_mask_selects_area():
    transform = Affine(1.0, 0.0, 7.0, 0.0, -1.0, 51.0)
    geom = {
        "type": "Polygon",
        "coordinates": [[[7.0, 50.0], [7.5, 50.0], [7.5, 51.0], [7.0, 51.0], [7.0, 50.0]]],
    }
    mask = polygon_mask(transform, (10, 10), geom)
    assert mask.any()
    assert mask.dtype == bool


def test_zonal_stats_median_and_clear_pct():
    ndvi = np.full((4, 4), 0.5, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    inside = np.ones((4, 4), dtype=bool)
    clear = np.array([[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 0, 0], [1, 1, 0, 0]], dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.median == pytest.approx(0.5)
    assert stats.clear_pct == pytest.approx(0.75)
    assert stats.pixels == 16
    assert stats.sufficient is True


def test_zonal_stats_too_few_pixels():
    ndvi = np.full((4, 4), 0.5, dtype=np.float32)
    inside = np.zeros((4, 4), dtype=bool)
    inside[0, 0] = True
    valid = np.ones((4, 4), dtype=bool)
    clear = np.ones((4, 4), dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.pixels == 1
    assert stats.sufficient is False
    assert stats.median is not None


def test_zonal_stats_all_nan_returns_none():
    ndvi = np.full((4, 4), np.nan, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    inside = np.ones((4, 4), dtype=bool)
    clear = np.zeros((4, 4), dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.median is None
    assert stats.mean is None
    assert stats.clear_pct == 0.0
    assert stats.sufficient is False
