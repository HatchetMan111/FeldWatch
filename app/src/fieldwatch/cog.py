from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.warp import Resampling, reproject

from .stac import SceneRef

RESAMPLING = {
    "red": Resampling.bilinear,
    "nir": Resampling.bilinear,
    "scl": Resampling.nearest,
}


@dataclass(frozen=True)
class Grid:
    crs: str
    transform: Affine
    width: int
    height: int


@dataclass(frozen=True)
class SceneArrays:
    red: np.ndarray
    nir: np.ndarray
    scl: np.ndarray


def _utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180.0) // 6.0) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


def make_grid(bbox: tuple[float, float, float, float], res_m: float = 10.0, max_px: int = 1024) -> Grid:
    lon_min, lat_min, lon_max, lat_max = bbox
    epsg = _utm_epsg((lon_min + lon_max) / 2.0, (lat_min + lat_max) / 2.0)
    crs = CRS.from_epsg(epsg)
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    points = [
        (lon_min, lat_min), (lon_max, lat_min), (lon_max, lat_max), (lon_min, lat_max),
        ((lon_min + lon_max) / 2.0, lat_min), ((lon_min + lon_max) / 2.0, lat_max),
        (lon_min, (lat_min + lat_max) / 2.0), (lon_max, (lat_min + lat_max) / 2.0),
    ]
    xs, ys = [], []
    for lon, lat in points:
        x, y = transformer.transform(lon, lat)
        xs.append(x)
        ys.append(y)

    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    width_m = max(right - left, res_m)
    height_m = max(top - bottom, res_m)

    factor = max(1.0, math.ceil(max(width_m, height_m) / (res_m * max_px)))
    pixel = res_m * factor
    width = max(1, int(math.ceil(width_m / pixel)))
    height = max(1, int(math.ceil(height_m / pixel)))
    transform = Affine.translation(left, top) * Affine.scale(width_m / width, -height_m / height)
    return Grid(crs=crs.to_string(), transform=transform, width=width, height=height)


def _read_asset(path: str, grid: Grid, resampling: Resampling) -> np.ndarray:
    destination = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination


def read_scene(scene: SceneRef, geometry: dict, grid: Grid) -> SceneArrays:
    return SceneArrays(
        red=_read_asset(scene.hrefs["red"], grid, RESAMPLING["red"]),
        nir=_read_asset(scene.hrefs["nir"], grid, RESAMPLING["nir"]),
        scl=_read_asset(scene.hrefs["scl"], grid, RESAMPLING["scl"]),
    )


class CogCache:
    def __init__(self, cache_dir: Path, max_bytes: int):
        self.dir = Path(cache_dir)
        self.max_bytes = max_bytes
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.dir / f"{digest}.npy"

    def get(self, key: str) -> np.ndarray | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return np.load(path)
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def put(self, key: str, array: np.ndarray) -> None:
        np.save(self._path(key), array)
        self.evict()

    def size(self) -> int:
        return sum(p.stat().st_size for p in self.dir.glob("*.npy"))

    def evict(self) -> None:
        files = sorted(self.dir.glob("*.npy"), key=lambda p: p.stat().st_mtime)
        total = self.size()
        for path in files:
            if total <= self.max_bytes:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)
