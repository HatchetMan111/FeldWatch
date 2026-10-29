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


def test_demand_with_missing_days_is_incomplete():
    eto = [DailyEto("2026-10-20", 1.0, None), DailyEto("2026-10-21", None, None), DailyEto("2026-10-22", 3.0, None)]
    out = demand_from(0.6, eto, area_m2=10_000.0)
    assert out["complete"] is False
    assert out["week_mm"] == pytest.approx(0.6 * 4.0)
    assert out["missing_days"] == 1
