from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import fiona
from shapely.geometry import Point, mapping, shape

from .geo import area_m2


@dataclass(frozen=True)
class Parcel:
    name: str
    geometry: dict
    area_m2: float


def _target(parcel_dir: Path, state: str) -> Path:
    return Path(parcel_dir) / f"{state.upper()}.fgb"


def import_file(source: Path, state: str, parcel_dir: Path) -> int:
    parcel_dir = Path(parcel_dir)
    parcel_dir.mkdir(parents=True, exist_ok=True)
    target = _target(parcel_dir, state)
    tmp = parcel_dir / f".{state.upper()}.tmp"
    if tmp.exists():
        shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink()
    count = 0
    schema = {"geometry": "Unknown", "properties": {"name": "str"}}
    with fiona.open(source) as src, fiona.open(
        tmp, "w", driver="FlatGeobuf", schema=schema, crs=src.crs
    ) as dst:
        for feature in src:
            geometry = feature["geometry"]
            if not geometry or geometry["type"] not in {"Polygon", "MultiPolygon"}:
                continue
            props = feature["properties"] or {}
            name = props.get("name") or props.get("FLIK") or f"{state}-{count + 1}"
            dst.write({"geometry": geometry, "properties": {"name": str(name)}})
            count += 1
    if target.exists():
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    tmp.replace(target)
    return count


class ParcelIndex:
    def __init__(self, parcel_dir: Path):
        self.dir = Path(parcel_dir)

    def available_states(self) -> list[str]:
        if not self.dir.exists():
            return []
        return sorted(p.stem for p in self.dir.glob("*.fgb"))

    def resolve(self, lon: float, lat: float, state: str) -> Parcel | None:
        path = _target(self.dir, state)
        if not path.exists():
            return None
        bbox = (lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01)
        point = Point(lon, lat)
        with fiona.open(path, bbox=bbox) as src:
            for feature in src:
                geometry = feature["geometry"]
                if not geometry:
                    continue
                geom = shape(geometry)
                if geom.contains(point):
                    props = feature["properties"] or {}
                    geo = dict(mapping(geom))
                    return Parcel(
                        name=str(props.get("name") or props.get("FLIK") or "Feld"),
                        geometry=geo,
                        area_m2=area_m2(geo),
                    )
        return None
