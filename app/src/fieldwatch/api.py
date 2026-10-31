from __future__ import annotations

import base64
import json
import shutil
import threading
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings, load_settings
from .db import (
    connect,
    create_field,
    delete_field,
    get_demand,
    get_field,
    get_observations,
    init_db,
    list_fields,
)
from .geo import area_m2, validate_polygon

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = Path(__file__).resolve().parents[2]
STATES_PATH = REPO_ROOT / "data" / "states.json"
WEB_DIST = APP_ROOT / "web" / "dist"


class FieldIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    geometry: dict


def _error(status: int, code: str, message: str, detail: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "detail": detail}},
    )


def _load_states() -> list[dict]:
    if not STATES_PATH.exists():
        return []
    return json.loads(STATES_PATH.read_text(encoding="utf-8"))["states"]


def _frame_payload(rows: list[dict]) -> dict:
    frames = []
    for row in rows:
        frame = row.get("frame")
        if not frame:
            continue
        width = row.get("frame_width") or 256
        height = row.get("frame_height") or 256
        frames.append(
            {
                "date": row["date"],
                "width": int(width),
                "height": int(height),
                "data": base64.b64encode(frame).decode("ascii"),
            }
        )
    return {"frames": frames}


def create_app(settings: Settings | None = None, *, conn=None, deps: dict | None = None) -> FastAPI:
    settings = settings or load_settings()
    deps = deps or {}
    own_conn = conn is None
    conn = conn or connect(settings.db_path)
    init_db(conn)

    api = FastAPI(
        title="FieldWatch",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    api.state.settings = settings
    api.state.conn = conn
    api.state.deps = deps
    jobs: dict[int, dict] = {}
    api.state.jobs = jobs

    @api.exception_handler(ValueError)
    async def _value_error(_request, exc: ValueError):
        return _error(422, "invalid_input", str(exc))

    @api.get("/healthz")
    def healthz():
        try:
            free = shutil.disk_usage(settings.data_dir).free
            disk_ok = free > 200 * 1024 * 1024
        except OSError:
            disk_ok = True
        return {
            "status": "ok" if disk_ok else "degraded",
            "version": __version__,
            "state": settings.state,
            "disk_ok": disk_ok,
            "db_ok": True,
        }

    @api.get("/api/states")
    def states():
        return {"states": _load_states()}

    @api.get("/api/resolve")
    def resolve(
        lat: float = Query(..., ge=-90, le=90),
        lon: float = Query(..., ge=-180, le=180),
    ):
        parcels = deps.get("parcels")
        if parcels is None:
            return {"found": False}
        hit = parcels.resolve(lon, lat, settings.state)
        if hit is None:
            return {"found": False}
        return {
            "found": True,
            "geometry": hit.geometry,
            "name": hit.name,
            "area_m2": hit.area_m2,
        }

    @api.get("/api/geocode")
    def geocode(q: str = Query(..., min_length=2)):
        resolver = deps.get("geocode")
        if resolver is None:
            from .geocode import search as geocode_search

            resolver = geocode_search
        hit = resolver(q)
        if hit is None:
            return {"found": False}
        return {"found": True, "label": hit.label, "lon": hit.lon, "lat": hit.lat}

    @api.post("/api/fields", status_code=201)
    def add_field(payload: FieldIn):
        validate_polygon(payload.geometry)
        field_id = create_field(
            conn,
            payload.name,
            payload.geometry,
            area_m2(payload.geometry),
            settings.state,
        )
        return {"id": field_id}

    @api.get("/api/fields")
    def fields():
        return {"fields": list_fields(conn)}

    @api.get("/api/fields/{field_id}")
    def field_detail(field_id: int):
        row = get_field(conn, field_id)
        if row is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return row

    @api.delete("/api/fields/{field_id}")
    def remove_field(field_id: int):
        if not delete_field(conn, field_id):
            return _error(404, "not_found", "Feld existiert nicht")
        return {"deleted": True}

    @api.get("/api/fields/{field_id}/series")
    def series(field_id: int, months: int = Query(12, ge=1, le=24)):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        cutoff = (date.today() - timedelta(days=int(months * 30.44))).isoformat()
        rows = [r for r in get_observations(conn, field_id) if r["date"] >= cutoff]
        return {
            "series": [
                {
                    "date": r["date"],
                    "median_ndvi": r["median_ndvi"],
                    "mean_ndvi": r["mean_ndvi"],
                    "clear_pct": r["clear_pct"],
                    "pixels": r["pixels"],
                }
                for r in rows
            ]
        }

    @api.get("/api/fields/{field_id}/frames")
    def frames(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return _frame_payload(get_observations(conn, field_id))

    @api.get("/api/fields/{field_id}/demand")
    def demand(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return get_demand(conn, field_id) or {
            "status": "unavailable",
            "reason": "not_analysed",
            "kcb": None,
            "etc_mm": [],
            "week_mm": None,
            "week_m3": None,
            "complete": False,
            "missing_days": settings.forecast_days,
        }

    @api.post("/api/fields/{field_id}/refresh", status_code=202)
    def refresh(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        runner = deps.get("analyse")
        if runner is None:
            return _error(503, "not_available", "Analyse ist nicht konfiguriert")
        if jobs.get(field_id, {}).get("running"):
            return {"status": "running"}

        def work():
            jobs[field_id] = {"running": True, "error": None}
            try:
                runner(field_id)
            except Exception as exc:  # noqa: BLE001 - Fehler wird an die UI gemeldet
                jobs[field_id] = {"running": False, "error": str(exc)}
            else:
                jobs[field_id] = {"running": False, "error": None}

        jobs[field_id] = {"running": True, "error": None}
        threading.Thread(target=work, daemon=True).start()
        return {"status": "started"}

    @api.get("/api/fields/{field_id}/status")
    def status(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        from .runtime import progress_for

        job = jobs.get(field_id, {"running": False, "error": None})
        progress = progress_for(field_id)
        return {
            "running": bool(job.get("running")),
            "error": job.get("error"),
            "observations": len(get_observations(conn, field_id)),
            "done": int(progress.get("done", 0)),
            "total": int(progress.get("total", 0)),
        }

    @api.get("/api/config")
    def config():
        return {
            "basemap": settings.basemap,
            "state": settings.state,
            "attribution": [
                "Contains modified Copernicus Sentinel data",
                "Weather data by Open-Meteo.com (CC BY 4.0)",
            ],
        }

    if WEB_DIST.exists():
        api.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    else:

        @api.get("/")
        def placeholder():
            return {"app": "fieldwatch", "ui": "not built"}

    return api


def app_factory() -> FastAPI:
    from .cog import CogCache
    from .runtime import analyse_field_by_id, build_deps
    from .scheduler import start_scheduler

    settings = load_settings()
    conn = connect(settings.db_path)
    cache = CogCache(settings.cache_dir, settings.cache_max_bytes)

    def analyse(field_id: int) -> dict:
        local = connect(settings.db_path)
        try:
            return analyse_field_by_id(field_id, settings=settings, conn=local, cache=cache)
        finally:
            local.close()

    deps = build_deps(settings, conn, cache)
    deps["analyse"] = analyse
    instance = create_app(settings, conn=conn, deps=deps)
    instance.state.scheduler = start_scheduler(settings, conn, cache)
    return instance
