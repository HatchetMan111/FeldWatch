from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .config import Settings
from .db import list_fields
from .runtime import analyse_field_by_id


def start_scheduler(settings: Settings, conn, cache):
    if not settings.scheduler_enabled:
        return None
    scheduler = BackgroundScheduler(timezone="UTC")

    def refresh_all():
        for field in list_fields(conn):
            try:
                analyse_field_by_id(field["id"], settings=settings, conn=conn, cache=cache)
            except Exception:
                continue

    scheduler.add_job(refresh_all, "cron", hour=3, minute=17, id="sentinel_refresh")
    scheduler.add_job(refresh_all, "interval", hours=1, id="weather_refresh")
    scheduler.start()
    return scheduler
