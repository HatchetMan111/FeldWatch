from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rasterio.features import geometry_mask
from shapely.geometry import shape


@dataclass(frozen=True)
class ZonalStats:
    median: float | None
    mean: float | None
    pixels: int
    clear_pct: float
    sufficient: bool


def polygon_mask(transform, shape_hw: tuple[int, int], geometry: dict) -> np.ndarray:
    return ~geometry_mask(
        [shape(geometry)],
        out_shape=shape_hw,
        transform=transform,
        invert=False,
        all_touched=False,
    )


def zonal_stats(
    ndvi: np.ndarray,
    valid: np.ndarray,
    inside: np.ndarray,
    clear: np.ndarray,
    min_pixels: int = 10,
) -> ZonalStats:
    inside = inside.astype(bool)
    pixels = int(inside.sum())
    clear_pct = float((clear & inside).sum()) / pixels if pixels else 0.0
    usable = inside & valid & np.isfinite(ndvi)
    values = ndvi[usable]
    if values.size == 0:
        return ZonalStats(None, None, pixels, clear_pct, False)
    return ZonalStats(
        median=float(np.median(values)),
        mean=float(np.mean(values)),
        pixels=pixels,
        clear_pct=clear_pct,
        sufficient=pixels >= min_pixels,
    )
