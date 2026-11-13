import pytest

from fieldwatch.weather import DailyEto, fetch_archive, fetch_forecast

GOOD = {
    "daily": {
        "time": ["2026-10-28", "2026-10-29", "2026-10-30"],
        "et0_fao_evapotranspiration": [1.2, 2.0, None],
        "precipitation_sum": [0.0, 3.5, None],
        "temperature_2m_max": [14.0, 12.5, None],
        "temperature_2m_min": [4.0, -1.5, None],
        "wind_speed_10m_max": [18.0, 24.0, None],
        "precipitation_probability_max": [10, 65, None],
        "soil_temperature_0_to_7cm_mean": [11.2, 9.8, None],
    }
}


def test_fetch_forecast_parses_values():
    calls = []

    def fake_fetch(url, params=None, timeout=20.0):
        calls.append((url, params))
        return GOOD

    out = fetch_forecast(51.0, 7.0, days=3, fetch=fake_fetch)
    assert len(out) == 3
    assert isinstance(out[0], DailyEto)
    assert out[0].date == "2026-10-28"
    assert out[0].eto_mm == pytest.approx(1.2)
    assert out[1].precip_mm == pytest.approx(3.5)
    assert "forecast" in calls[0][0]
    assert calls[0][1]["latitude"] == 51.0
    assert out[0].t_max_c == pytest.approx(14.0)
    assert out[0].soil_temp_c == pytest.approx(11.2)
    assert out[1].t_min_c == pytest.approx(-1.5)
    assert out[1].wind_max_kmh == pytest.approx(24.0)
    assert out[1].precip_prob_pct == pytest.approx(65.0)
    daily_fields = calls[0][1]["daily"]
    for field in (
        "temperature_2m_max",
        "temperature_2m_min",
        "wind_speed_10m_max",
        "precipitation_probability_max",
        "soil_temperature_0_to_7cm_mean",
    ):
        assert field in daily_fields


def test_fetch_forecast_keeps_null_as_none():
    out = fetch_forecast(51.0, 7.0, days=3, fetch=lambda *a, **k: GOOD)
    assert out[2].eto_mm is None
    assert out[2].precip_mm is None
    assert out[2].t_min_c is None
    assert out[2].wind_max_kmh is None
    assert out[2].precip_prob_pct is None
    assert out[2].soil_temp_c is None


def test_fetch_forecast_tolerates_missing_new_fields():
    """Alte/abweichende Antworten (ohne neue Felder) brechen nicht ab."""
    payload = {
        "daily": {
            "time": ["2026-10-28"],
            "et0_fao_evapotranspiration": [1.0],
            "precipitation_sum": [0.0],
        }
    }
    out = fetch_forecast(51.0, 7.0, days=1, fetch=lambda *a, **k: payload)
    assert out[0].eto_mm == pytest.approx(1.0)
    assert out[0].t_max_c is None
    assert out[0].t_min_c is None
    assert out[0].wind_max_kmh is None
    assert out[0].precip_prob_pct is None
    assert out[0].soil_temp_c is None


def test_fetch_forecast_missing_key_raises():
    with pytest.raises(ValueError, match="daily"):
        fetch_forecast(51.0, 7.0, fetch=lambda *a, **k: {"error": True})


def test_fetch_forecast_shorter_than_requested_stays_short():
    payload = {
        "daily": {
            "time": ["2026-10-28"],
            "et0_fao_evapotranspiration": [1.0],
            "precipitation_sum": [0.0],
        }
    }
    out = fetch_forecast(51.0, 7.0, days=7, fetch=lambda *a, **k: payload)
    assert len(out) == 1


def test_fetch_archive_uses_archive_host():
    calls = []

    def fake_fetch(url, params=None, timeout=20.0):
        calls.append(url)
        return GOOD

    out = fetch_archive(51.0, 7.0, "2025-10-28", "2025-10-30", fetch=fake_fetch)
    assert len(out) == 3
    assert "archive-api" in calls[0]
