import pytest

from fieldwatch.model import canopy_from_ndvi, demand_from
from fieldwatch.weather import DailyEto


def test_canopy_clamps_low():
    cc, kcb = canopy_from_ndvi(0.0)
    assert cc == pytest.approx(0.0)
    assert kcb == pytest.approx(0.14)


def test_canopy_normal():
    cc, kcb = canopy_from_ndvi(0.5)
    assert cc == pytest.approx(1.22 * 0.5 - 0.21)
    assert kcb == pytest.approx(1.13 * cc + 0.14)


def test_canopy_clamps_high():
    cc, kcb = canopy_from_ndvi(0.95)
    assert cc == pytest.approx(0.8)
    assert kcb == pytest.approx(1.13 * 0.8 + 0.14)


def test_demand_sum_and_volume():
    eto = [DailyEto(f"2026-10-{20+i:02d}", v, 0.0) for i, v in enumerate([1.0, 2.0, 3.0, 0.0, 1.0, 1.0, 1.0])]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["week_mm"] == pytest.approx(0.6 * 9.0)
    assert out["week_m3"] == pytest.approx(0.6 * 9.0 * 10_000.0 / 1000.0)
    assert out["complete"] is True
    assert len(out["etc_mm"]) == 7


def test_demand_carries_weather_fields():
    eto = [
        DailyEto("2026-10-20", 1.0, 5.0, t_max_c=14.0, t_min_c=6.0, wind_max_kmh=12.0, precip_prob_pct=20, soil_temp_c=11.0),
        DailyEto("2026-10-21", 2.0, None, t_max_c=15.0, t_min_c=1.0, wind_max_kmh=25.0, precip_prob_pct=0, soil_temp_c=10.0),
        DailyEto("2026-10-22", None, 2.0, t_max_c=None, t_min_c=None, wind_max_kmh=None, precip_prob_pct=None, soil_temp_c=None),
    ]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["temp_max_c"] == [14.0, 15.0, None]
    assert out["temp_min_c"] == [6.0, 1.0, None]
    assert out["wind_max_kmh"] == [12.0, 25.0, None]
    assert out["precip_prob_pct"] == [20.0, 0.0, None]
    assert out["soil_temp_c"] == [11.0, 10.0, None]


def test_demand_balance_over_common_days():
    # Tag 1: Bedarf 0.6*1=0.6, Regen 5.0 -> Bilanz +4.4; Tag 2: kein Regen -> nur Tag 1 zaehlt
    eto = [DailyEto("2026-10-20", 1.0, 5.0), DailyEto("2026-10-21", 2.0, None)]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["balance_mm"] == pytest.approx(5.0 - 0.6)


def test_demand_balance_negative_and_none():
    eto = [DailyEto("2026-10-20", 2.0, 0.0), DailyEto("2026-10-21", 1.0, None)]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["balance_mm"] == pytest.approx(0.0 - 1.2)
    assert demand_from(0.6, [DailyEto("2026-10-20", 1.0, None)], 1.0)["balance_mm"] is None


def test_demand_with_missing_days_is_incomplete():
    eto = [DailyEto("2026-10-20", 1.0, None), DailyEto("2026-10-21", None, None), DailyEto("2026-10-22", 3.0, None)]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["complete"] is False
    assert out["week_mm"] == pytest.approx(0.6 * 4.0)
    assert out["missing_days"] == 1
