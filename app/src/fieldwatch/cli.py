from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .cog import make_grid, read_scene
from .config import Settings, load_settings
from .geo import bbox_of, buffer_bbox, square_around
from .pipeline import analyse_field
from .stac import search
from .weather import fetch_forecast


def build_runtime(settings: Settings) -> dict:
    return {
        "search": lambda geometry, months, max_cloud: search(
            geometry, months=months, max_cloud=max_cloud
        ),
        "grid": lambda geometry: make_grid(buffer_bbox(bbox_of(geometry), 0.10)),
        "arrays": lambda scene, geometry, grid: read_scene(scene, geometry, grid),
        "forecast": lambda lat, lon, days: fetch_forecast(lat, lon, days=days),
    }


def run_point(
    lat: float,
    lon: float,
    radius_m: float,
    *,
    settings: Settings | None = None,
    runtime: dict | None = None,
    today: date | None = None,
) -> dict:
    settings = settings or load_settings()
    runtime = runtime or build_runtime(settings)
    geometry = square_around(lon, lat, radius_m)
    grid = runtime["grid"](geometry)
    scenes = runtime["search"](geometry, settings.history_months, settings.max_cloud_cover)
    forecast = runtime["forecast"](lat, lon, settings.forecast_days)
    result = analyse_field(
        geometry,
        scenes=scenes,
        arrays_for=lambda scene: runtime["arrays"](scene, geometry, grid),
        forecast=forecast,
        grid=grid,
        min_clear_pct=settings.min_clear_pct,
        stale_days=settings.stale_days,
        today=today,
    )
    return {
        "geometry": geometry,
        "observations": [
            {k: v for k, v in obs.items() if k != "frame"} for obs in result.observations
        ],
        "demand": result.demand,
        "flags": result.flags,
        "scenes_found": len(scenes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fieldwatch")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Ein Feld um einen Punkt analysieren")
    run.add_argument("--lat", type=float, required=True)
    run.add_argument("--lon", type=float, required=True)
    run.add_argument("--radius", type=float, default=100.0, help="Halbkante in Metern")
    run.add_argument("--out", type=Path, default=None)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    payload = run_point(args.lat, args.lon, args.radius)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"geschrieben: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
