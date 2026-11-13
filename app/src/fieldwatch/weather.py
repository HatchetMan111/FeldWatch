from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from .http import get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = (
    "et0_fao_evapotranspiration,precipitation_sum,"
    "temperature_2m_max,temperature_2m_min,wind_speed_10m_max,"
    "precipitation_probability_max,soil_temperature_0_to_7cm_mean"
)

_forecast_get = partial(get_json, retries=2)


@dataclass(frozen=True)
class DailyEto:
    date: str
    eto_mm: float | None
    precip_mm: float | None
    t_max_c: float | None = None
    t_min_c: float | None = None
    wind_max_kmh: float | None = None
    precip_prob_pct: float | None = None
    soil_temp_c: float | None = None


def _rows(payload: dict) -> list[DailyEto]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Open-Meteo-Antwort ohne 'daily'-Block")
    dates = daily.get("time") or []
    eto = daily.get("et0_fao_evapotranspiration") or []
    precip = daily.get("precipitation_sum") or []
    t_max = daily.get("temperature_2m_max") or []
    t_min = daily.get("temperature_2m_min") or []
    wind = daily.get("wind_speed_10m_max") or []
    prob = daily.get("precipitation_probability_max") or []
    soil = daily.get("soil_temperature_0_to_7cm_mean") or []

    def pick(seq, i):
        value = seq[i] if i < len(seq) else None
        return None if value is None else float(value)

    return [
        DailyEto(
            date=str(d),
            eto_mm=pick(eto, i),
            precip_mm=pick(precip, i),
            t_max_c=pick(t_max, i),
            t_min_c=pick(t_min, i),
            wind_max_kmh=pick(wind, i),
            precip_prob_pct=pick(prob, i),
            soil_temp_c=pick(soil, i),
        )
        for i, d in enumerate(dates)
    ]


def fetch_forecast(lat: float, lon: float, days: int = 7, *, fetch=None) -> list[DailyEto]:
    fetch = fetch or _forecast_get
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
