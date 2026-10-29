from __future__ import annotations

from .weather import DailyEto

CC_MIN = 0.0
CC_MAX = 0.8


def canopy_from_ndvi(ndvi: float) -> tuple[float, float]:
    cc = 1.22 * float(ndvi) - 0.21
    cc = min(max(cc, CC_MIN), CC_MAX)
    kcb = 1.13 * cc + 0.14
    return cc, kcb


def demand_from(kcb: float, eto: list[DailyEto | None], area_m2: float) -> dict:
    etc: list[float | None] = []
    for day in eto:
        value = None if day is None else day.eto_mm
        etc.append(None if value is None else round(kcb * value, 3))
    valid = [v for v in etc if v is not None]
    week_mm = round(sum(valid), 3)
    missing = sum(1 for v in etc if v is None)
    return {
        "kcb": round(kcb, 4),
        "etc_mm": etc,
        "week_mm": week_mm,
        "week_m3": round(week_mm * float(area_m2) / 1000.0, 1),
        "area_m2": round(float(area_m2), 1),
        "complete": missing == 0 and len(etc) > 0,
        "missing_days": missing,
    }
