from __future__ import annotations

from datetime import date

DROP_THRESHOLD = 0.15
DROP_WINDOW_DAYS = 14
SEASONAL_THRESHOLD = 0.15
SEASONAL_WINDOW_DAYS = 21
SEASONAL_MIN_BASELINE = 2

ANOMALY_TEXT = {
    "sudden_drop": "NDVI-Einbruch gegenueber der vorherigen Aufnahme (Hagel, Mahd, Wasserstand?).",
    "seasonal_deficit": "NDVI deutlich unter dem gleichen Zeitraum in frueheren Jahren.",
}


def _anniversary_gap(past: date, ref: date) -> int:
    """Tage zwischen `past` und dem Jahrestag von `ref` im Jahr von `past`."""
    try:
        anniversary = ref.replace(year=past.year)
    except ValueError:  # 29. Februar in einem Nicht-Schaltjahr
        anniversary = ref.replace(year=past.year, day=28)
    return abs((past - anniversary).days)


def detect_anomalies(observations: list[dict]) -> list[dict]:
    """Findet auffaellige NDVI-Beobachtungen ueber die ganze Historie.

    sudden_drop: NDVI faellt um >= 0.15 gegenueber der vorherigen Aufnahme,
        wenn diese maximal 14 Tage zurueckliegt (kurzfristiges Ereignis).
    seasonal_deficit: NDVI liegt >= 0.15 unter dem Mittelwert der gleichen
        Jahreszeit aus frueheren Jahren (+-21 Tage, mindestens 2 Vergleiche).
    """
    points: list[tuple[date, float]] = sorted(
        (
            (date.fromisoformat(o["date"]), float(o["median_ndvi"]))
            for o in observations
            if o.get("median_ndvi") is not None
        ),
        key=lambda p: p[0],
    )
    anomalies: list[dict] = []
    for i, (day, ndvi) in enumerate(points):
        if i > 0:
            prev_day, prev_ndvi = points[i - 1]
            if (day - prev_day).days <= DROP_WINDOW_DAYS and ndvi <= prev_ndvi - DROP_THRESHOLD:
                anomalies.append(
                    {
                        "date": day.isoformat(),
                        "type": "sudden_drop",
                        "ndvi": round(ndvi, 4),
                        "baseline": round(prev_ndvi, 4),
                        "delta": round(ndvi - prev_ndvi, 4),
                    }
                )

        baseline = [
            ndvi_prev
            for day_prev, ndvi_prev in points[:i]
            if day_prev.year < day.year
            and _anniversary_gap(day_prev, day) <= SEASONAL_WINDOW_DAYS
        ]
        if len(baseline) >= SEASONAL_MIN_BASELINE:
            mean = sum(baseline) / len(baseline)
            if ndvi <= mean - SEASONAL_THRESHOLD:
                anomalies.append(
                    {
                        "date": day.isoformat(),
                        "type": "seasonal_deficit",
                        "ndvi": round(ndvi, 4),
                        "baseline": round(mean, 4),
                        "delta": round(ndvi - mean, 4),
                    }
                )
    return anomalies
