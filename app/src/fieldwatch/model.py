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
    week_mm = round(sum(valid), 3) if valid else None
    missing = sum(1 for v in etc if v is None)

    # Bilanz nur ueber Tage, an denen Bedarf UND Regen bekannt sind.
    pairs = [
        (day.precip_mm, v)
        for day, v in zip(eto, etc)
        if day is not None and day.precip_mm is not None and v is not None
    ]
    balance_mm = (
        round(sum(p for p, _ in pairs) - sum(e for _, e in pairs), 2) if pairs else None
    )

    def series(getattr_name: str) -> list[float | None]:
        return [None if day is None else getattr(day, getattr_name) for day in eto]

    return {
        "kcb": round(kcb, 4),
        "etc_mm": etc,
        "precip_mm": [None if day is None else day.precip_mm for day in eto],
        "dates": [day.date if day is not None else None for day in eto],
        "temp_max_c": series("t_max_c"),
        "temp_min_c": series("t_min_c"),
        "wind_max_kmh": series("wind_max_kmh"),
        "precip_prob_pct": series("precip_prob_pct"),
        "soil_temp_c": series("soil_temp_c"),
        "week_mm": week_mm,
        "week_m3": None if week_mm is None else round(week_mm * float(area_m2) / 1000.0, 1),
        "balance_mm": balance_mm,
        "area_m2": round(float(area_m2), 1),
        "complete": missing == 0 and len(etc) > 0,
        "missing_days": missing,
    }
