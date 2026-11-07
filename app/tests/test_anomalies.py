import pytest

from fieldwatch.anomalies import detect_anomalies


def _obs(date: str, ndvi: float | None):
    return {"date": date, "median_ndvi": ndvi}


def test_no_anomalies_on_steady_history():
    rows = [
        _obs("2025-04-01", 0.60),
        _obs("2025-05-01", 0.65),
        _obs("2026-04-02", 0.61),
        _obs("2026-05-01", 0.63),
    ]
    assert detect_anomalies(rows) == []


def test_sudden_drop_is_flagged():
    rows = [
        _obs("2026-05-10", 0.70),
        _obs("2026-05-18", 0.40),
    ]
    anomalies = detect_anomalies(rows)
    assert len(anomalies) == 1
    assert anomalies[0]["type"] == "sudden_drop"
    assert anomalies[0]["date"] == "2026-05-18"
    assert anomalies[0]["baseline"] == 0.7
    assert anomalies[0]["delta"] == pytest.approx(-0.3)


def test_gradual_decline_is_not_a_sudden_drop():
    rows = [
        _obs("2026-08-01", 0.70),
        _obs("2026-08-12", 0.62),
        _obs("2026-08-24", 0.54),
    ]
    assert detect_anomalies(rows) == []


def test_large_gap_is_not_a_sudden_drop():
    rows = [
        _obs("2026-03-01", 0.70),
        _obs("2026-04-05", 0.35),
    ]
    assert detect_anomalies(rows) == []


def test_seasonal_deficit_needs_baseline_from_earlier_years():
    # Nur ein Vorjahreswert: zu wenig Verankerung, keine Meldung.
    rows = [
        _obs("2025-04-15", 0.70),
        _obs("2026-04-10", 0.30),
    ]
    assert detect_anomalies(rows) == []


def test_seasonal_deficit_is_flagged():
    rows = [
        _obs("2024-04-15", 0.70),
        _obs("2024-05-05", 0.68),
        _obs("2025-04-20", 0.66),
        _obs("2025-05-01", 0.70),
        _obs("2026-04-12", 0.35),
    ]
    anomalies = detect_anomalies(rows)
    assert [a["type"] for a in anomalies] == ["seasonal_deficit"]
    assert anomalies[0]["date"] == "2026-04-12"
    assert anomalies[0]["baseline"] == pytest.approx(0.6867, abs=1e-3)


def test_null_ndvi_rows_are_ignored():
    rows = [_obs("2026-05-10", None), _obs("2026-05-18", None)]
    assert detect_anomalies(rows) == []


def test_feb_29_anniversary_does_not_crash():
    rows = [
        _obs("2024-02-29", 0.70),
        _obs("2024-03-05", 0.72),
        _obs("2027-02-26", 0.40),
    ]
    anomalies = detect_anomalies(rows)
    assert all(a["type"] == "seasonal_deficit" for a in anomalies)
