from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import numpy as np

from .cog import Grid, SceneArrays, project_geometry
from .geo import area_m2
from .indices import clear_fraction, clear_mask, ndvi_array, to_uint8_frame
from .model import canopy_from_ndvi, demand_from
from .stac import SceneRef
from .weather import DailyEto
from .zonal import polygon_mask, zonal_stats


@dataclass
class AnalyseResult:
    observations: list[dict] = field(default_factory=list)
    demand: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _empty_demand(reason: str, forecast_size: int) -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "kcb": None,
        "etc_mm": [],
        "week_mm": None,
        "week_m3": None,
        "complete": False,
        "missing_days": forecast_size,
    }


def analyse_field(
    geometry: dict,
    *,
    scenes: list[SceneRef],
    arrays_for: Callable[[SceneRef], SceneArrays],
    forecast: list[DailyEto | None],
    grid: Grid,
    min_clear_pct: float = 0.70,
    stale_days: int = 21,
    today: date | None = None,
    workers: int = 1,
    progress: Callable[[int, int], None] | None = None,
) -> AnalyseResult:
    today = today or date.today()
    result = AnalyseResult()
    inside = polygon_mask(grid.transform, (grid.height, grid.width), project_geometry(geometry, grid))
    if not inside.any():
        result.flags.extend(["insufficient_pixels", "no_clear_observation"])
        result.demand = _empty_demand("insufficient_pixels", len(forecast))
        return result

    ordered = sorted(scenes, key=lambda s: s.datetime)
    total = len(ordered)
    done = 0
    batch_size = max(1, workers * 2)
    for start in range(0, total, batch_size):
        chunk = ordered[start : start + batch_size]
        if workers > 1 and len(chunk) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {scene.id: pool.submit(arrays_for, scene) for scene in chunk}
                arrays_by_id = {scene.id: futures[scene.id].result() for scene in chunk}
        else:
            arrays_by_id = {scene.id: arrays_for(scene) for scene in chunk}

        for scene in chunk:
            arrays = arrays_by_id[scene.id]
            done += 1
            valid = np.isfinite(arrays.red) & np.isfinite(arrays.nir)
            ndvi = ndvi_array(arrays.red, arrays.nir)
            scl = np.nan_to_num(arrays.scl, nan=0).astype(np.uint8)
            clear = clear_mask(scl)
            if progress is not None:
                progress(done, total)
            if clear_fraction(clear, inside) < min_clear_pct:
                continue
            stats = zonal_stats(ndvi, valid & clear, inside, clear)
            if stats.median is None:
                continue
            if not stats.sufficient and "insufficient_pixels" not in result.flags:
                result.flags.append("insufficient_pixels")
            frame = to_uint8_frame(ndvi, valid & clear & inside)
            result.observations.append(
                {
                    "date": _parse_date(scene.datetime).isoformat(),
                    "median_ndvi": round(stats.median, 4),
                    "mean_ndvi": round(stats.mean, 4) if stats.mean is not None else None,
                    "clear_pct": round(stats.clear_pct, 4),
                    "pixels": stats.pixels,
                    "frame": frame.tobytes(),
                    "frame_width": int(frame.shape[1]),
                    "frame_height": int(frame.shape[0]),
                }
            )

    if not result.observations:
        result.flags.append("no_clear_observation")
        result.demand = _empty_demand("no_clear_observation", len(forecast))
        return result

    latest = result.observations[-1]
    age = (today - date.fromisoformat(latest["date"])).days
    if age > stale_days:
        result.flags.append("stale_canopy")

    cc, kcb = canopy_from_ndvi(latest["median_ndvi"])
    missing = sum(1 for day in forecast if day is None or day.eto_mm is None)
    demand = demand_from(kcb, forecast, area_m2(geometry))
    demand["cover"] = round(cc, 4)
    demand["canopy_date"] = latest["date"]
    demand["canopy_age_days"] = age
    if missing == 0:
        demand["status"] = "ok"
    elif missing < len(forecast):
        demand["status"] = "partial"
    else:
        demand["status"] = "unavailable"
    result.demand = demand
    return result
