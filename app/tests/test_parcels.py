import json
from pathlib import Path

import fiona
import pytest
from fiona.crs import from_epsg
from shapely.geometry import mapping, Polygon

from fieldwatch.parcels import ParcelIndex, import_file

SQUARE = Polygon([(7.0, 51.0), (7.01, 51.0), (7.01, 51.01), (7.0, 51.01)])


def _write_geojson(path: Path) -> Path:
    schema = {"geometry": "Polygon", "properties": {"name": "str"}}
    with fiona.open(
        path, "w", driver="GeoJSON", schema=schema, crs=from_epsg(4326)
    ) as dst:
        dst.write({"geometry": mapping(SQUARE), "properties": {"name": "Testfeld"}})
    return path


def test_import_and_resolve(tmp_path):
    source = _write_geojson(tmp_path / "src.geojson")
    count = import_file(source, "NW", tmp_path)
    assert count == 1
    index = ParcelIndex(tmp_path)
    assert index.available_states() == ["NW"]
    hit = index.resolve(7.005, 51.005, "NW")
    assert hit is not None
    assert hit.name == "Testfeld"
    assert hit.area_m2 > 0


def test_resolve_miss_returns_none(tmp_path):
    source = _write_geojson(tmp_path / "src.geojson")
    import_file(source, "NW", tmp_path)
    index = ParcelIndex(tmp_path)
    assert index.resolve(8.0, 51.0, "NW") is None


def test_resolve_unknown_state_returns_none(tmp_path):
    index = ParcelIndex(tmp_path)
    assert index.available_states() == []
    assert index.resolve(7.0, 51.0, "BY") is None


def test_import_is_idempotent(tmp_path):
    source = _write_geojson(tmp_path / "src.geojson")
    assert import_file(source, "NW", tmp_path) == 1
    assert import_file(source, "NW", tmp_path) == 1
    assert len(list(Path(tmp_path).glob("NW.fgb"))) == 1
