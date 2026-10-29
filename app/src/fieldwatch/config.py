from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    state: str = "none"
    port: int = 8080
    basemap: str = "local"
    data_dir: Path = Path("/var/lib/fieldwatch")
    repo_ref: str = "main"
    forecast_days: int = 7
    history_months: int = 12
    max_cloud_cover: int = 80
    min_clear_pct: float = 0.70
    stale_days: int = 21
    cache_max_bytes: int = 4 * 1024**3
    scheduler_enabled: bool = True

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def parcel_dir(self) -> Path:
        return self.data_dir / "parcels"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.sqlite"


def _int(env: Mapping[str, str], key: str, default: int, minimum: int = 1) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{key} muss >= {minimum} sein, war {value}")
    return value


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    e = environ if env is None else env
    return Settings(
        state=e.get("FIELDWATCH_STATE", "none") or "none",
        port=_int(e, "FIELDWATCH_PORT", 8080),
        basemap=e.get("FIELDWATCH_BASEMAP", "local") or "local",
        data_dir=Path(e.get("FIELDWATCH_DATA_DIR", "/var/lib/fieldwatch")),
        repo_ref=e.get("FIELDWATCH_REPO_REF", "main") or "main",
        forecast_days=_int(e, "FIELDWATCH_FORECAST_DAYS", 7),
        history_months=_int(e, "FIELDWATCH_HISTORY_MONTHS", 12),
        max_cloud_cover=_int(e, "FIELDWATCH_MAX_CLOUD_COVER", 80, minimum=0),
        min_clear_pct=_float(e, "FIELDWATCH_MIN_CLEAR_PCT", 0.70),
        stale_days=_int(e, "FIELDWATCH_STALE_DAYS", 21),
        cache_max_bytes=_int(e, "FIELDWATCH_CACHE_MAX_BYTES", 4 * 1024**3),
        scheduler_enabled=(e.get("FIELDWATCH_SCHEDULER", "1") != "0"),
    )
