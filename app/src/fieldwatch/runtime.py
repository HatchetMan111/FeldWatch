from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

from .cog import CogCache, SceneArrays, make_grid, read_scene
from .config import Settings
from .db import get_field, log_source, save_demand, save_observations
from .geo import bbox_of, buffer_bbox, centroid
from .parcels import ParcelIndex
from .pipeline import analyse_field
from .stac import search
from .weather import fetch_forecast

CACHE_KEY = "{scene_id}:{asset}:{grid_crs}:{grid_w}x{grid_h}"
PROGRESS: dict[int, dict] = {}


def progress_for(field_id: int) -> dict:
    return dict(PROGRESS.get(field_id, {}))


def _default_clients(settings: Settings, cache: CogCache) -> dict:
    def _grid(geometry):
        return make_grid(buffer_bbox(bbox_of(geometry), 0.10))

    def _arrays(scene, geometry, grid):
        key = CACHE_KEY.format(
            scene_id=scene.id, asset="rgb", grid_crs=grid.crs,
            grid_w=grid.width, grid_h=grid.height,
        )
        hit = cache.get(key)
        if hit is not None and getattr(hit, "shape", (0,))[0] == 3:
            return SceneArrays(red=hit[0], nir=hit[1], scl=hit[2])
        arrays = read_scene(scene, geometry, grid)
        cache.put(key, np.stack([arrays.red, arrays.nir, arrays.scl]))
        return arrays

    return {
        "search": lambda geometry, months, max_cloud: search(
            geometry, months=months, max_cloud=max_cloud
        ),
        "grid": _grid,
        "arrays": _arrays,
        "forecast": lambda lat, lon, days: fetch_forecast(lat, lon, days=days),
    }


def analyse_field_by_id(
    field_id: int,
    *,
    settings: Settings,
    conn,
    cache,
    clients: dict | None = None,
    today: date | None = None,
) -> dict:
    field = get_field(conn, field_id)
    if field is None:
        raise KeyError(f"Feld {field_id} existiert nicht")

    clients = clients or _default_clients(settings, cache)
    geometry = field["geometry"]
    grid = clients["grid"](geometry)
    scenes = clients["search"](geometry, settings.history_months, settings.max_cloud_cover)
    lon, lat = centroid(geometry)
    forecast = clients["forecast"](lat, lon, settings.forecast_days)

    PROGRESS[field_id] = {"done": 0, "total": len(scenes)}

    def _progress(done: int, total: int) -> None:
        PROGRESS[field_id] = {"done": done, "total": total}

    result = analyse_field(
        geometry,
        scenes=scenes,
        arrays_for=lambda scene: clients["arrays"](scene, geometry, grid),
        forecast=forecast,
        grid=grid,
        min_clear_pct=settings.min_clear_pct,
        stale_days=settings.stale_days,
        today=today,
        workers=4,
        progress=_progress,
    )

    save_observations(conn, field_id, result.observations)
    save_demand(conn, field_id, {**result.demand, "flags": result.flags})
    log_source(
        conn,
        "stac",
        "https://earth-search.aws.element84.com/v1/search",
        200,
        len(scenes),
        0,
        "Copernicus",
    )
    return {"demand": result.demand, "flags": result.flags, "observations": len(result.observations)}


def build_deps(settings: Settings, conn, cache=None) -> dict:
    cache = cache or CogCache(settings.cache_dir, settings.cache_max_bytes)
    return {
        "parcels": ParcelIndex(settings.parcel_dir),
        "analyse": lambda field_id: analyse_field_by_id(
            field_id, settings=settings, conn=conn, cache=cache
        ),
    }
