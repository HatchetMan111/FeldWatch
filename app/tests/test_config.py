from fieldwatch import __version__


def test_version_is_set():
    assert __version__ == "0.1.0"


from pathlib import Path

import pytest

from fieldwatch.config import Settings, load_settings


def test_defaults():
    s = load_settings({})
    assert isinstance(s, Settings)
    assert s.port == 8080
    assert s.state == "none"
    assert s.basemap == "local"
    assert s.forecast_days == 7
    assert s.history_months == 12
    assert s.max_cloud_cover == 80
    assert s.min_clear_pct == pytest.approx(0.70)
    assert s.stale_days == 21
    assert s.data_dir == Path("/var/lib/fieldwatch")


def test_env_overrides():
    s = load_settings(
        {
            "FIELDWATCH_PORT": "9090",
            "FIELDWATCH_STATE": "NW",
            "FIELDWATCH_BASEMAP": "osm",
            "FIELDWATCH_DATA_DIR": "/tmp/fw",
            "FIELDWATCH_MIN_CLEAR_PCT": "0.5",
        }
    )
    assert s.port == 9090
    assert s.state == "NW"
    assert s.basemap == "osm"
    assert s.data_dir == Path("/tmp/fw")
    assert s.min_clear_pct == pytest.approx(0.5)


def test_invalid_port_rejected():
    with pytest.raises(ValueError):
        load_settings({"FIELDWATCH_PORT": "0"})
