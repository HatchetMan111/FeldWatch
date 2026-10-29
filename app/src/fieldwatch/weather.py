from __future__ import annotations

from dataclasses import dataclass

from .http import get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = "et0_fao_evapotranspiration,precipitation_sum"


@dataclass(frozen=True)
class DailyEto:
    date: str
    eto_mm: float | None
    precip_mm: float | None


def _rows(payload: dict) -> list[DailyEto]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Open-Meteo-Antwort ohne 'daily'-Block")
    dates = daily.get("time") or []
    eto = daily.get("et0_fao_evapotranspiration") or []
    precip = daily.get("precipitation_sum") or []

    def pick(seq, i):
        value = seq[i] if i < len(seq) else None
        return None if value is None else float(value)

    return [
        DailyEto(date=str(d), eto_mm=pick(eto, i), precip_mm=pick(precip, i))
        for i, d in enumerate(dates)
    ]


def fetch_forecast(lat: float, lon: float, days: int = 7, *, fetch=get_json) -> list[DailyEto]:
    payload = fetch(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": DAILY_FIELDS,
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    return _rows(payload)


def fetch_archive(lat: float, lon: float, start: str, end: str, *, fetch=get_json) -> list[DailyEto]:
    payload = fetch(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": DAILY_FIELDS,
            "timezone": "auto",
        },
    )
    return _rows(payload)
