# FieldWatch MVP – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen Proxmox-LXC per Einzeiler installieren, der eine LAN-only Web-App mit echter Sentinel-2-Wachstumsanimation und 7-Tage-Wasserbedarf pro Feld bereitstellt.

**Architecture:** Ein unprivilegierter Debian-12-LXC, ein systemd-Dienst (`uvicorn`), FastAPI liefert REST-API und gebautes Frontend. Die Pipeline (`STAC → COG-Window → NDVI/SCL → Zonal → CC/Kcb → Open-Meteo ETo`) läuft im selben Prozess, Ergebnisse liegen in SQLite, COG-Fenster in einem LRU-Cache. Installer zweigeteilt: Host-Script erzeugt den CT, Inner-Script provisioniert die App.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, httpx, numpy, rasterio, pyproj, shapely, fiona, APScheduler, SQLite (stdlib), React 18 + TypeScript + Vite + MapLibre GL, Bash 5, systemd, Proxmox `pct`/`pveam`/`pvesh`.

**Spec:** `docs/superpowers/specs/2026-10-28-fieldwatch-design.md`

## Global Constraints

- Repo: `https://github.com/HatchetMan111/FeldWatch`, Ref `main`.
- `APP_ID="fieldwatch"`, `CT_HOSTNAME="fieldwatch"`, Service `fieldwatch.service`, Port `8080`.
- Raw-Base: `https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main`.
- Installer-Scripts beginnen mit `set -euo pipefail`, definieren `msg_info/msg_ok/msg_warn/msg_error/die`, schreiben ein Log und haben einen `ERR`-Trap, der Exit-Code, Zeile, Befehl, Host-Log, Container-Log, `pct status` und `journalctl` ausgibt.
- LXC: Debian 12, unprivileged, `onboot=1`, 2 vCPU, 2048 MB RAM, 2048 MB Swap, 16 GB Disk, `vmbr0`, DHCP.
- App bindet `0.0.0.0:8080`. `ufw` erlaubt den Port **nur** aus `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- Kein TLS, keine Domain, kein Port-Forwarding, kein Login.
- Intern SI: mm und m³. Umrechnung nur in der UI.
- Pflicht-Attribution im Footer: „Contains modified Copernicus Sentinel data", „Weather data by Open-Meteo.com (CC BY 4.0)".
- Kein Code, Design, Text oder Logo von `epicfields.app` übernehmen.
- Alle Python-Module unter `app/src/fieldwatch/`, Tests unter `app/tests/`.
- Kein Node im Container: `app/web/dist/` wird im Repo mitgeliefert.

## Review Focus

Diese Fälle sind in der Spec nicht ausformuliert, würden Nutzer aber real treffen. Jeder bekommt einen Test in dem Task, der den Code besitzt:

1. **Feld an einer UTM-Zonengrenze** — das Zielraster darf nicht kollabieren (Breite/Höhe ≥ 1, Pixelgröße endlich). Test in Task 8.
2. **Pixel mit `nir + red == 0`** (Wasser, Schatten, Nodata) — NDVI muss `NaN` liefern, nicht `inf`/Crash. Test in Task 4.
3. **Szene komplett bewölkt** (Clear-Anteil 0) — Ergebnis ist „keine Beobachtung" mit Flag, kein NDVI 0. Test in Task 10.
4. **Open-Meteo liefert `null` oder weniger als 7 Tage** — Demand degradiert auf `unavailable`, die API antwortet weiter mit 200. Test in Task 6 und Task 11.
5. **Feld kleiner als ~10 Pixel** — Zonalstatistik meldet `insufficient` statt stillschweigend 0 mm. Test in Task 5 und Task 10.

---

## File Structure

```text
FeldWatch/
├── .gitignore
├── README.md
├── NOTICE
├── data/
│   └── states.json
├── app/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── src/fieldwatch/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── http.py
│   │   ├── geo.py
│   │   ├── model.py
│   │   ├── indices.py
│   │   ├── zonal.py
│   │   ├── weather.py
│   │   ├── stac.py
│   │   ├── cog.py
│   │   ├── db.py
│   │   ├── parcels.py
│   │   ├── pipeline.py
│   │   ├── scheduler.py
│   │   ├── api.py
│   │   └── cli.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   ├── test_geo.py
│   │   ├── test_model.py
│   │   ├── test_indices.py
│   │   ├── test_zonal.py
│   │   ├── test_weather.py
│   │   ├── test_stac.py
│   │   ├── test_cog.py
│   │   ├── test_db.py
│   │   ├── test_pipeline.py
│   │   ├── test_api.py
│   │   ├── test_runtime.py
│   │   ├── test_cli.py
│   │   └── test_parcels.py
│   └── web/
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       ├── dist/
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           ├── api.ts
│           ├── frames.ts
│           ├── Map.tsx
│           ├── Timeline.tsx
│           ├── Demand.tsx
│           ├── Method.tsx
│           ├── frames.test.ts
│           └── styles.css
├── install/
│   ├── fieldwatch.sh
│   └── fieldwatch-inner.sh
├── systemd/
│   └── fieldwatch.service
└── tests/
    ├── static-checks.sh
    └── reboot-test.sh
```

**Verantwortlichkeiten:**

| Datei | Aufgabe |
|---|---|
| `config.py` | Einzige Stelle, die Umgebungsvariablen liest |
| `http.py` | HTTP-JSON mit User-Agent, Timeout, injizierbar für Tests |
| `geo.py` | reine Geometrie-Helfer, keine I/O |
| `model.py` | reine Mathematik, keine I/O |
| `indices.py` | reine Array-Operationen |
| `zonal.py` | Rastermaske + Statistik |
| `stac.py` / `weather.py` | je ein externer Dienst, `fetch`-Callable injizierbar |
| `cog.py` | Raster-I/O und Cache, einzige Stelle mit rasterio |
| `db.py` | einzige Stelle mit SQL |
| `pipeline.py` | verdrahtet alles, kennt keine HTTP-Details |
| `api.py` | HTTP-Schicht, ruft nur `pipeline`/`db` |
| `parcels.py` | Feldblock-Lookup, kennt kein HTTP |

---

## Task 1: Repo-Gerüst und Testlauf

**Files:**
- Create: `.gitignore`, `app/pyproject.toml`, `app/requirements.txt`, `app/src/fieldwatch/__init__.py`, `app/tests/conftest.py`, `app/tests/test_config.py`, `tests/static-checks.sh`

**Interfaces:**
- Consumes: nichts
- Produces: lauffähige `pytest`-Umgebung, `fieldwatch.__version__`

- [ ] **Step 1: `.gitignore` schreiben**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
app/web/node_modules/
*.log
*.trace
/var/
.DS_Store
```

- [ ] **Step 2: `app/requirements.txt` schreiben**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
numpy==2.2.1
rasterio==1.4.3
pyproj==3.7.0
shapely==2.0.6
fiona==1.10.1
affine==2.4.0
APScheduler==3.11.0
pydantic==2.10.4
```

- [ ] **Step 3: `app/pyproject.toml` schreiben**

```toml
[project]
name = "fieldwatch"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 4: `app/src/fieldwatch/__init__.py` schreiben**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: `app/tests/conftest.py` schreiben**

```python
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 6: Failing Test für Version schreiben**

`app/tests/test_config.py`:

```python
from fieldwatch import __version__


def test_version_is_set():
    assert __version__ == "0.1.0"
```

- [ ] **Step 7: Test laufen lassen (muss fehlschlagen)**

Run: `cd app && python3 -m venv .venv && .venv/bin/pip install -q pytest && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (1 passed) — `conftest.py` macht `src/` importierbar; ohne `conftest.py` wäre es `ModuleNotFoundError`.

- [ ] **Step 8: Abhängigkeiten installieren und Tests grün bekommen**

```bash
cd app
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q -e .
.venv/bin/python -m pytest tests/test_config.py -v
```

Expected: PASS (1 passed)

- [ ] **Step 9: Platzhalter `tests/static-checks.sh` anlegen (Task 21 füllt ihn)**

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "static-checks: noch nicht implementiert"
```

- [ ] **Step 10: Commit**

```bash
chmod +x tests/static-checks.sh
git add .gitignore app/pyproject.toml app/requirements.txt app/src/fieldwatch/__init__.py app/tests/conftest.py app/tests/test_config.py tests/static-checks.sh
git commit -m "chore: project skeleton and pytest harness"
```

---

## Task 2: Settings aus Umgebung

**Files:**
- Create: `app/src/fieldwatch/config.py`
- Test: `app/tests/test_config.py` (erweitern)

**Interfaces:**
- Consumes: nichts
- Produces: `Settings` (frozen dataclass), `load_settings(env: Mapping[str,str] | None = None) -> Settings`, Properties `cache_dir`, `parcel_dir`, `db_path`

- [ ] **Step 1: Failing Test schreiben**

```python
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
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.config'`

- [ ] **Step 3: `config.py` implementieren**

```python
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
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/config.py app/tests/test_config.py
git commit -m "feat: settings from environment"
```

---

## Task 3: Geometrie-Helfer

**Files:**
- Create: `app/src/fieldwatch/geo.py`
- Test: `app/tests/test_geo.py`

**Interfaces:**
- Consumes: nichts
- Produces:
  - `bbox_of(geometry: dict) -> tuple[float, float, float, float]`
  - `area_m2(geometry: dict) -> float`
  - `centroid(geometry: dict) -> tuple[float, float]`
  - `validate_polygon(geometry: dict) -> None`
  - `buffer_bbox(bbox, pct: float = 0.10) -> tuple[float, float, float, float]`
  - `square_around(lon: float, lat: float, radius_m: float) -> dict`
  - `point_in_geometry(lon: float, lat: float, geometry: dict) -> bool`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_geo.py`:

```python
import pytest

from fieldwatch.geo import (
    area_m2,
    bbox_of,
    buffer_bbox,
    centroid,
    point_in_geometry,
    square_around,
    validate_polygon,
)

SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]
    ],
}


def test_bbox():
    assert bbox_of(SQUARE) == pytest.approx((7.0, 51.0, 7.01, 51.01))


def test_area_is_plausible():
    assert 700_000 < area_m2(SQUARE) < 900_000


def test_area_of_polygon_with_hole():
    outer = SQUARE["coordinates"][0]
    hole = [[7.004, 51.004], [7.006, 51.004], [7.006, 51.006], [7.004, 51.006], [7.004, 51.004]]
    geom = {"type": "Polygon", "coordinates": [outer, hole]}
    assert area_m2(geom) < area_m2(SQUARE)


def test_centroid_inside_square():
    lon, lat = centroid(SQUARE)
    assert lon == pytest.approx(7.005, abs=1e-6)
    assert lat == pytest.approx(51.005, abs=1e-6)


def test_validate_rejects_point():
    with pytest.raises(ValueError, match="Polygon"):
        validate_polygon({"type": "Point", "coordinates": [7.0, 51.0]})


def test_validate_rejects_unclosed_ring():
    bad = {"type": "Polygon", "coordinates": [[[7.0, 51.0], [7.1, 51.0], [7.1, 51.1]]]}
    with pytest.raises(ValueError, match="geschlossen"):
        validate_polygon(bad)


def test_validate_accepts_multipolygon():
    validate_polygon({"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]})


def test_buffer_bbox_grows():
    out = buffer_bbox((7.0, 51.0, 7.01, 51.01), 0.1)
    assert out[0] < 7.0 and out[2] > 7.01


def test_square_around_is_valid_and_has_area():
    poly = square_around(7.0, 51.0, 500.0)
    validate_polygon(poly)
    assert area_m2(poly) == pytest.approx(1_000_000, rel=0.15)


def test_point_in_geometry():
    assert point_in_geometry(7.005, 51.005, SQUARE)
    assert not point_in_geometry(7.0, 51.0, SQUARE)
    assert not point_in_geometry(8.0, 51.0, SQUARE)
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_geo.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.geo'`

- [ ] **Step 3: `geo.py` implementieren**

```python
from __future__ import annotations

import math

from pyproj import Geod
from shapely.geometry import Point, shape

_GEOD = Geod(ellps="WGS84")


def _as_shapes(geometry: dict):
    kind = geometry.get("type")
    if kind == "Polygon":
        return [geometry]
    if kind == "MultiPolygon":
        return [{"type": "Polygon", "coordinates": c} for c in geometry["coordinates"]]
    raise ValueError(f"Erwartet Polygon oder MultiPolygon, war {kind!r}")


def validate_polygon(geometry: dict) -> None:
    if not isinstance(geometry, dict):
        raise ValueError("Geometrie muss ein GeoJSON-Objekt sein")
    shapes = _as_shapes(geometry)
    if not shapes:
        raise ValueError("Polygon enthält keine Ringe")
    for poly in shapes:
        rings = poly["coordinates"]
        if not rings:
            raise ValueError("Polygon enthält einen leeren Ring")
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("Ring braucht mindestens 4 Punkte und muss geschlossen sein")
            if list(ring[0]) != list(ring[-1]):
                raise ValueError("Ring muss geschlossen sein (erster == letzter Punkt)")
    if not shape(geometry).is_valid:
        raise ValueError("Polygon ist selbstüberschneidend oder ungültig")


def bbox_of(geometry: dict) -> tuple[float, float, float, float]:
    shapes = [shape(p) for p in _as_shapes(geometry)]
    return (
        min(s.bounds[0] for s in shapes),
        min(s.bounds[1] for s in shapes),
        max(s.bounds[2] for s in shapes),
        max(s.bounds[3] for s in shapes),
    )


def area_m2(geometry: dict) -> float:
    area, _ = _GEOD.geometry_area_perimeter(shape(geometry))
    return abs(area)


def centroid(geometry: dict) -> tuple[float, float]:
    c = shape(geometry).centroid
    return c.x, c.y


def buffer_bbox(bbox: tuple[float, float, float, float], pct: float = 0.10):
    lon_min, lat_min, lon_max, lat_max = bbox
    dx = (lon_max - lon_min) * pct
    dy = (lat_max - lat_min) * pct
    return (lon_min - dx, lat_min - dy, lon_max + dx, lat_max + dy)


def square_around(lon: float, lat: float, radius_m: float) -> dict:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    ring = [
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    return shape(geometry).contains(Point(lon, lat))
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_geo.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/geo.py app/tests/test_geo.py
git commit -m "feat: geojson helpers for bbox, area, centroid"
```

---

## Task 4: NDVI, SCL-Maske und Frames

**Files:**
- Create: `app/src/fieldwatch/indices.py`
- Test: `app/tests/test_indices.py`

**Interfaces:**
- Consumes: nichts
- Produces:
  - `VALID_SCL: frozenset[int]`, `NDVI_MIN = -0.2`, `NDVI_MAX = 1.0`, `FRAME_SIZE = 256`
  - `ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray`
  - `clear_mask(scl: np.ndarray, valid: frozenset[int] = VALID_SCL) -> np.ndarray`
  - `clear_fraction(mask: np.ndarray, inside: np.ndarray) -> float`
  - `to_uint8_frame(ndvi: np.ndarray, valid: np.ndarray, size: int = FRAME_SIZE) -> np.ndarray`
  - `from_uint8_frame(frame: np.ndarray) -> np.ndarray`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_indices.py`:

```python
import numpy as np
import pytest

from fieldwatch.indices import (
    NDVI_MAX,
    NDVI_MIN,
    clear_fraction,
    clear_mask,
    from_uint8_frame,
    ndvi_array,
    to_uint8_frame,
)


def test_ndvi_simple():
    red = np.array([[0.1, 0.2]], dtype=np.float32)
    nir = np.array([[0.5, 0.2]], dtype=np.float32)
    out = ndvi_array(red, nir)
    assert out[0, 0] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1))
    assert out[0, 1] == pytest.approx(0.0)


def test_ndvi_zero_sum_is_nan_not_inf():
    red = np.array([[0.0]], dtype=np.float32)
    nir = np.array([[0.0]], dtype=np.float32)
    out = ndvi_array(red, nir)
    assert np.isnan(out[0, 0])
    assert not np.isinf(out[0, 0])


def test_ndvi_negative_sum_is_nan():
    out = ndvi_array(np.array([[-0.5]], dtype=np.float32), np.array([[0.2]], dtype=np.float32))
    assert np.isnan(out[0, 0])


def test_clear_mask_keeps_vegetation_and_bare_soil():
    scl = np.array([[4, 5, 7, 3, 8, 9, 10, 11, 0, 6]], dtype=np.uint8)
    mask = clear_mask(scl)
    assert mask.tolist() == [[True, True, True, False, False, False, False, False, False, False]]


def test_clear_fraction_ignores_outside():
    scl = np.array([[4, 4], [8, 8]], dtype=np.uint8)
    inside = np.array([[True, False], [True, False]])
    assert clear_fraction(clear_mask(scl), inside) == pytest.approx(0.5)


def test_clear_fraction_all_outside_is_zero():
    scl = np.array([[4]], dtype=np.uint8)
    inside = np.array([[False]])
    assert clear_fraction(clear_mask(scl), inside) == 0.0


def test_uint8_roundtrip():
    ndvi = np.array([[-0.2, 0.0, 0.5, 1.0]], dtype=np.float32)
    valid = np.array([[True, True, True, True]])
    frame = to_uint8_frame(ndvi, valid)
    assert frame.dtype == np.uint8
    back = from_uint8_frame(frame)
    np.testing.assert_allclose(back, ndvi, atol=(NDVI_MAX - NDVI_MIN) / 254 * 1.5)


def test_uint8_invalid_pixels_are_zero():
    ndvi = np.array([[0.5, np.nan]], dtype=np.float32)
    valid = np.array([[True, False]])
    frame = to_uint8_frame(ndvi, valid)
    assert frame[0, 1] == 0
    assert np.isnan(from_uint8_frame(frame)[0, 1])


def test_frame_is_downsampled_to_max_size():
    ndvi = np.full((600, 400), 0.5, dtype=np.float32)
    valid = np.ones((600, 400), dtype=bool)
    frame = to_uint8_frame(ndvi, valid, size=256)
    assert max(frame.shape) <= 256
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_indices.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.indices'`

- [ ] **Step 3: `indices.py` implementieren**

```python
from __future__ import annotations

import numpy as np

VALID_SCL = frozenset({4, 5, 7})
NDVI_MIN = -0.2
NDVI_MAX = 1.0
FRAME_SIZE = 256


def ndvi_array(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    red = red.astype(np.float32, copy=False)
    nir = nir.astype(np.float32, copy=False)
    denom = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / denom
    ndvi = np.where(denom > 0, ndvi, np.nan)
    ndvi = np.where(np.isfinite(ndvi), ndvi, np.nan)
    return np.clip(ndvi, -1.0, 1.0).astype(np.float32)


def clear_mask(scl: np.ndarray, valid: frozenset[int] = VALID_SCL) -> np.ndarray:
    return np.isin(scl, np.fromiter(valid, dtype=np.uint8))


def clear_fraction(mask: np.ndarray, inside: np.ndarray) -> float:
    total = int(inside.sum())
    if total == 0:
        return 0.0
    return float((mask & inside).sum()) / total


def _block_reduce(data: np.ndarray, factor: int, mask: np.ndarray | None) -> np.ndarray:
    if factor <= 1:
        return data
    h, w = data.shape
    ph = (-h) % factor
    pw = (-w) % factor
    if ph or pw:
        data = np.pad(data, ((0, ph), (0, pw)), mode="edge")
        if mask is not None:
            mask = np.pad(mask, ((0, ph), (0, pw)), mode="constant", constant_values=False)
    h, w = data.shape
    reshaped = data.reshape(h // factor, factor, w // factor, factor)
    with np.errstate(invalid="ignore"):
        if mask is None:
            return np.nanmean(reshaped, axis=(1, 3))
        masked = np.where(mask.reshape(h // factor, factor, w // factor, factor), reshaped, np.nan)
        return np.nanmean(masked, axis=(1, 3))


def to_uint8_frame(ndvi: np.ndarray, valid: np.ndarray, size: int = FRAME_SIZE) -> np.ndarray:
    data = np.where(valid & np.isfinite(ndvi), ndvi, np.nan).astype(np.float32)
    factor = max(1, int(np.ceil(max(data.shape) / size)))
    reduced = _block_reduce(data, factor, valid)
    scaled = (reduced - NDVI_MIN) / (NDVI_MAX - NDVI_MIN)
    scaled = np.clip(scaled * 254.0 + 1.0, 1.0, 255.0)
    return np.where(np.isfinite(reduced), scaled, 0.0).astype(np.uint8)


def from_uint8_frame(frame: np.ndarray) -> np.ndarray:
    frame = frame.astype(np.float32)
    ndvi = (frame - 1.0) / 254.0 * (NDVI_MAX - NDVI_MIN) + NDVI_MIN
    return np.where(frame > 0, ndvi, np.nan).astype(np.float32)
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_indices.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/indices.py app/tests/test_indices.py
git commit -m "feat: ndvi, scl cloud mask and compact frames"
```

---

## Task 5: Zonalstatistik

**Files:**
- Create: `app/src/fieldwatch/zonal.py`
- Test: `app/tests/test_zonal.py`

**Interfaces:**
- Consumes: `numpy`, `rasterio.features`, `shapely`
- Produces:
  - `ZonalStats` dataclass: `median: float | None`, `mean: float | None`, `pixels: int`, `clear_pct: float`, `sufficient: bool`
  - `polygon_mask(transform, shape_hw: tuple[int,int], geometry: dict) -> np.ndarray`
  - `zonal_stats(ndvi, valid, inside, clear, min_pixels: int = 10) -> ZonalStats`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_zonal.py`:

```python
import numpy as np
import pytest
from affine import Affine

from fieldwatch.zonal import polygon_mask, zonal_stats


def test_polygon_mask_selects_area():
    transform = Affine(1.0, 0.0, 7.0, 0.0, -1.0, 51.0)
    geom = {
        "type": "Polygon",
        "coordinates": [[[7.0, 50.0], [7.5, 50.0], [7.5, 51.0], [7.0, 51.0], [7.0, 50.0]]],
    }
    mask = polygon_mask(transform, (10, 10), geom)
    assert mask.any()
    assert mask.dtype == bool


def test_zonal_stats_median_and_clear_pct():
    ndvi = np.full((4, 4), 0.5, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    inside = np.ones((4, 4), dtype=bool)
    clear = np.array([[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 0, 0], [1, 1, 0, 0]], dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.median == pytest.approx(0.5)
    assert stats.clear_pct == pytest.approx(0.75)
    assert stats.pixels == 16
    assert stats.sufficient is True


def test_zonal_stats_too_few_pixels():
    ndvi = np.full((4, 4), 0.5, dtype=np.float32)
    inside = np.zeros((4, 4), dtype=bool)
    inside[0, 0] = True
    valid = np.ones((4, 4), dtype=bool)
    clear = np.ones((4, 4), dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.pixels == 1
    assert stats.sufficient is False
    assert stats.median is not None


def test_zonal_stats_all_nan_returns_none():
    ndvi = np.full((4, 4), np.nan, dtype=np.float32)
    valid = np.ones((4, 4), dtype=bool)
    inside = np.ones((4, 4), dtype=bool)
    clear = np.zeros((4, 4), dtype=bool)
    stats = zonal_stats(ndvi, valid, inside, clear)
    assert stats.median is None
    assert stats.mean is None
    assert stats.clear_pct == 0.0
    assert stats.sufficient is False
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_zonal.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.zonal'`

- [ ] **Step 3: `zonal.py` implementieren**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rasterio.features import geometry_mask
from shapely.geometry import shape


@dataclass(frozen=True)
class ZonalStats:
    median: float | None
    mean: float | None
    pixels: int
    clear_pct: float
    sufficient: bool


def polygon_mask(transform, shape_hw: tuple[int, int], geometry: dict) -> np.ndarray:
    return ~geometry_mask(
        [shape(geometry)],
        out_shape=shape_hw,
        transform=transform,
        invert=False,
        all_touched=False,
    )


def zonal_stats(
    ndvi: np.ndarray,
    valid: np.ndarray,
    inside: np.ndarray,
    clear: np.ndarray,
    min_pixels: int = 10,
) -> ZonalStats:
    inside = inside.astype(bool)
    pixels = int(inside.sum())
    clear_pct = float((clear & inside).sum()) / pixels if pixels else 0.0
    usable = inside & valid & np.isfinite(ndvi)
    values = ndvi[usable]
    if values.size == 0:
        return ZonalStats(None, None, pixels, clear_pct, False)
    return ZonalStats(
        median=float(np.median(values)),
        mean=float(np.mean(values)),
        pixels=pixels,
        clear_pct=clear_pct,
        sufficient=pixels >= min_pixels,
    )
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_zonal.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/zonal.py app/tests/test_zonal.py
git commit -m "feat: zonal statistics over field polygon"
```

---

## Task 6: Open-Meteo-Client

**Files:**
- Create: `app/src/fieldwatch/http.py`, `app/src/fieldwatch/weather.py`
- Test: `app/tests/test_weather.py`

**Interfaces:**
- Consumes: `httpx`
- Produces:
  - `get_json(url: str, params: dict | None = None, timeout: float = 20.0) -> dict`
  - `DailyEto` dataclass: `date: str`, `eto_mm: float | None`, `precip_mm: float | None`
  - `fetch_forecast(lat, lon, days=7, *, fetch=get_json) -> list[DailyEto]`
  - `fetch_archive(lat, lon, start, end, *, fetch=get_json) -> list[DailyEto]`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_weather.py`:

```python
import pytest

from fieldwatch.weather import DailyEto, fetch_archive, fetch_forecast

GOOD = {
    "daily": {
        "time": ["2026-10-28", "2026-10-29", "2026-10-30"],
        "et0_fao_evapotranspiration": [1.2, 2.0, None],
        "precipitation_sum": [0.0, 3.5, None],
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


def test_fetch_forecast_keeps_null_as_none():
    out = fetch_forecast(51.0, 7.0, days=3, fetch=lambda *a, **k: GOOD)
    assert out[2].eto_mm is None
    assert out[2].precip_mm is None


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
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_weather.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.weather'`

- [ ] **Step 3: `http.py` implementieren**

```python
from __future__ import annotations

import httpx

USER_AGENT = "FieldWatch/0.1 (self-hosted; +https://github.com/HatchetMan111/FeldWatch)"


def get_json(url: str, params: dict | None = None, timeout: float = 20.0) -> dict:
    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: `weather.py` implementieren**

```python
from __future__ import annotations

from dataclasses import dataclass

from .http import get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = "et0_fao_evapotranspiration,precipitation_sum"


@dataclass(frozen=True)
class DailyEto:
    date: str
    eto_mm: float | None
    precip_mm: float | None


def _rows(payload: dict) -> list[DailyEto]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Open-Meteo-Antwort ohne 'daily'-Block")
    dates = daily.get("time") or []
    eto = daily.get("et0_fao_evapotranspiration") or []
    precip = daily.get("precipitation_sum") or []

    def pick(seq, i):
        value = seq[i] if i < len(seq) else None
        return None if value is None else float(value)

    return [
        DailyEto(date=str(d), eto_mm=pick(eto, i), precip_mm=pick(precip, i))
        for i, d in enumerate(dates)
    ]


def fetch_forecast(lat: float, lon: float, days: int = 7, *, fetch=get_json) -> list[DailyEto]:
    payload = fetch(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": DAILY_FIELDS,
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    return _rows(payload)


def fetch_archive(lat: float, lon: float, start: str, end: str, *, fetch=get_json) -> list[DailyEto]:
    payload = fetch(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": DAILY_FIELDS,
            "timezone": "auto",
        },
    )
    return _rows(payload)
```

- [ ] **Step 5: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_weather.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add app/src/fieldwatch/http.py app/src/fieldwatch/weather.py app/tests/test_weather.py
git commit -m "feat: open-meteo et0 client"
```

---

## Task 7: STAC-Client

**Files:**
- Create: `app/src/fieldwatch/stac.py`
- Test: `app/tests/test_stac.py`

**Interfaces:**
- Consumes: `get_json`
- Produces:
  - `SceneRef` dataclass: `id: str`, `datetime: str`, `cloud_cover: float`, `hrefs: dict[str, str]`
  - `ASSETS = ("red", "nir", "scl")`
  - `search(geometry, months=12, max_cloud=80, *, limit=500, now=None, fetch=get_json) -> list[SceneRef]`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_stac.py`:

```python
import pytest

from fieldwatch.stac import SceneRef, search

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}

PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S2B_old",
            "properties": {"datetime": "2026-01-01T10:00:00Z", "eo:cloud_cover": 12.0},
            "assets": {
                "red": {"href": "https://example/red_old.tif"},
                "nir": {"href": "https://example/nir_old.tif"},
                "scl": {"href": "https://example/scl_old.tif"},
                "visual": {"href": "https://example/visual_old.tif"},
            },
        },
        {
            "id": "S2A_new",
            "properties": {"datetime": "2026-10-01T10:00:00Z", "eo:cloud_cover": 3.0},
            "assets": {
                "red": {"href": "https://example/red_new.tif"},
                "nir": {"href": "https://example/nir_new.tif"},
                "scl": {"href": "https://example/scl_new.tif"},
            },
        },
        {
            "id": "S2A_incomplete",
            "properties": {"datetime": "2026-09-01T10:00:00Z", "eo:cloud_cover": 1.0},
            "assets": {"red": {"href": "https://example/red.tif"}},
        },
    ],
}


def test_search_returns_sorted_and_complete():
    scenes = search(SQUARE, fetch=lambda *a, **k: PAYLOAD)
    assert [s.id for s in scenes] == ["S2A_new", "S2B_old"]
    assert all(isinstance(s, SceneRef) for s in scenes)
    assert scenes[0].hrefs["nir"].endswith("nir_new.tif")


def test_search_request_has_expected_fields():
    seen = {}

    def fake_fetch(url, params=None, timeout=20.0):
        seen["url"] = url
        seen["params"] = params
        return PAYLOAD

    search(SQUARE, months=6, max_cloud=50, fetch=fake_fetch)
    assert "earth-search" in seen["url"]
    assert seen["params"]["collections"] == "sentinel-2-l2a"
    assert seen["params"]["query"]["eo:cloud_cover"]["lt"] == 50
    assert seen["params"]["intersects"]["type"] == "Polygon"
    assert seen["params"]["datetime"].endswith("Z/..")


def test_search_empty_collection():
    assert search(SQUARE, fetch=lambda *a, **k: {"features": []}) == []


def test_search_missing_features_raises():
    with pytest.raises(ValueError, match="features"):
        search(SQUARE, fetch=lambda *a, **k: {})
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_stac.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.stac'`

- [ ] **Step 3: `stac.py` implementieren**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .http import get_json

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
ASSETS = ("red", "nir", "scl")


@dataclass(frozen=True)
class SceneRef:
    id: str
    datetime: str
    cloud_cover: float
    hrefs: dict[str, str]


def _window(months: int, now: datetime | None) -> str:
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=int(months * 30.44))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return f"{start.strftime(fmt)}/.."


def search(
    geometry: dict,
    months: int = 12,
    max_cloud: int = 80,
    *,
    limit: int = 500,
    now: datetime | None = None,
    fetch=get_json,
) -> list[SceneRef]:
    payload = fetch(
        STAC_URL,
        {
            "collections": COLLECTION,
            "intersects": geometry,
            "datetime": _window(months, now),
            "query": {"eo:cloud_cover": {"lt": max_cloud}},
            "limit": limit,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        },
    )
    features = payload.get("features")
    if features is None:
        raise ValueError("STAC-Antwort ohne 'features'")

    scenes: list[SceneRef] = []
    for feature in features:
        assets = feature.get("assets") or {}
        hrefs = {
            key: assets[key]["href"]
            for key in ASSETS
            if key in assets and "href" in assets[key]
        }
        if len(hrefs) != len(ASSETS):
            continue
        props = feature.get("properties") or {}
        scenes.append(
            SceneRef(
                id=feature.get("id", ""),
                datetime=props.get("datetime", ""),
                cloud_cover=float(props.get("eo:cloud_cover", 100.0)),
                hrefs=hrefs,
            )
        )
    scenes.sort(key=lambda s: s.datetime, reverse=True)
    return scenes
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_stac.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/stac.py app/tests/test_stac.py
git commit -m "feat: earth-search stac client"
```

---

## Task 8: Rastergitter, Fenster-Read und Cache

**Files:**
- Create: `app/src/fieldwatch/cog.py`
- Test: `app/tests/test_cog.py`

**Interfaces:**
- Consumes: `rasterio`, `numpy`, `pyproj`, `affine`
- Produces:
  - `Grid` dataclass: `crs: str`, `transform: Affine`, `width: int`, `height: int`
  - `SceneArrays` dataclass: `red`, `nir`, `scl` (`np.ndarray`)
  - `make_grid(bbox, res_m=10.0, max_px=1024) -> Grid`
  - `read_scene(scene: SceneRef, geometry: dict, grid: Grid) -> SceneArrays`
  - `CogCache(cache_dir: Path, max_bytes: int)` mit `.get(key)`, `.put(key, arr)`, `.size()`, `.evict()`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_cog.py`:

```python
from pathlib import Path

import numpy as np
import pytest
import rasterio

from fieldwatch.cog import CogCache, Grid, make_grid, read_scene
from fieldwatch.stac import SceneRef

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


def test_make_grid_produces_10m_pixels():
    grid = make_grid((7.0, 51.0, 7.01, 51.01), res_m=10.0)
    assert grid.crs.startswith("EPSG:32")
    assert grid.width > 50
    assert grid.height > 50
    assert 8.0 < abs(grid.transform.a) < 12.0


def test_make_grid_caps_size():
    grid = make_grid((6.0, 50.0, 8.0, 52.0), res_m=10.0, max_px=256)
    assert grid.width <= 256
    assert grid.height <= 256
    assert grid.width >= 1 and grid.height >= 1


def test_make_grid_at_zone_border_does_not_collapse():
    grid = make_grid((5.99, 51.0, 6.01, 51.002), res_m=10.0)
    assert grid.width >= 1
    assert grid.height >= 1
    assert np.isfinite(grid.transform.a)
    assert abs(grid.transform.a) > 0


def _write_tif(path: Path, value: int, grid) -> Path:
    data = np.full((grid.height, grid.width), value, dtype=np.uint16)
    with rasterio.open(
        path, "w", driver="GTiff", width=grid.width, height=grid.height, count=1,
        dtype="uint16", crs=grid.crs, transform=grid.transform,
    ) as dst:
        dst.write(data, 1)
    return path


def test_read_scene_reprojects_into_grid(tmp_path):
    grid = make_grid((7.0, 51.0, 7.01, 51.01))
    red = _write_tif(tmp_path / "red.tif", 100, grid)
    nir = _write_tif(tmp_path / "nir.tif", 500, grid)
    scl = _write_tif(tmp_path / "scl.tif", 4, grid)
    scene = SceneRef(
        id="x", datetime="2026-10-01T10:00:00Z", cloud_cover=0.0,
        hrefs={"red": str(red), "nir": str(nir), "scl": str(scl)},
    )
    arrays = read_scene(scene, SQUARE, grid)
    assert arrays.red.shape == (grid.height, grid.width)
    assert arrays.scl.shape == (grid.height, grid.width)
    assert float(np.nanmedian(arrays.nir)) == pytest.approx(500, abs=1)


def test_cache_evicts_oldest(tmp_path):
    cache = CogCache(tmp_path, max_bytes=3000)
    cache.put("a", np.zeros((40, 40), dtype=np.float32))
    cache.put("b", np.zeros((40, 40), dtype=np.float32))
    cache.put("c", np.zeros((40, 40), dtype=np.float32))
    assert cache.size() <= 3000
    assert cache.get("a") is None


def test_cache_roundtrip(tmp_path):
    cache = CogCache(tmp_path, max_bytes=10_000_000)
    arr = np.arange(100, dtype=np.float32).reshape(10, 10)
    cache.put("k", arr)
    np.testing.assert_array_equal(cache.get("k"), arr)
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_cog.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.cog'`

- [ ] **Step 3: `cog.py` implementieren**

```python
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.warp import Resampling, reproject

from .stac import SceneRef

RESAMPLING = {
    "red": Resampling.bilinear,
    "nir": Resampling.bilinear,
    "scl": Resampling.nearest,
}


@dataclass(frozen=True)
class Grid:
    crs: str
    transform: Affine
    width: int
    height: int


@dataclass(frozen=True)
class SceneArrays:
    red: np.ndarray
    nir: np.ndarray
    scl: np.ndarray


def _utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180.0) // 6.0) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


def make_grid(bbox: tuple[float, float, float, float], res_m: float = 10.0, max_px: int = 1024) -> Grid:
    lon_min, lat_min, lon_max, lat_max = bbox
    epsg = _utm_epsg((lon_min + lon_max) / 2.0, (lat_min + lat_max) / 2.0)
    crs = CRS.from_epsg(epsg)
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    points = [
        (lon_min, lat_min), (lon_max, lat_min), (lon_max, lat_max), (lon_min, lat_max),
        ((lon_min + lon_max) / 2.0, lat_min), ((lon_min + lon_max) / 2.0, lat_max),
        (lon_min, (lat_min + lat_max) / 2.0), (lon_max, (lat_min + lat_max) / 2.0),
    ]
    xs, ys = [], []
    for lon, lat in points:
        x, y = transformer.transform(lon, lat)
        xs.append(x)
        ys.append(y)

    left, right = min(xs), max(xs)
    bottom, top = min(ys), max(ys)
    width_m = max(right - left, res_m)
    height_m = max(top - bottom, res_m)

    factor = max(1.0, math.ceil(max(width_m, height_m) / (res_m * max_px)))
    pixel = res_m * factor
    width = max(1, int(math.ceil(width_m / pixel)))
    height = max(1, int(math.ceil(height_m / pixel)))
    transform = Affine.translation(left, top) * Affine.scale(width_m / width, -height_m / height)
    return Grid(crs=crs.to_string(), transform=transform, width=width, height=height)


def _read_asset(path: str, grid: Grid, resampling: Resampling) -> np.ndarray:
    destination = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination


def read_scene(scene: SceneRef, geometry: dict, grid: Grid) -> SceneArrays:
    return SceneArrays(
        red=_read_asset(scene.hrefs["red"], grid, RESAMPLING["red"]),
        nir=_read_asset(scene.hrefs["nir"], grid, RESAMPLING["nir"]),
        scl=_read_asset(scene.hrefs["scl"], grid, RESAMPLING["scl"]),
    )


class CogCache:
    def __init__(self, cache_dir: Path, max_bytes: int):
        self.dir = Path(cache_dir)
        self.max_bytes = max_bytes
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self.dir / f"{digest}.npy"

    def get(self, key: str) -> np.ndarray | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return np.load(path)
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def put(self, key: str, array: np.ndarray) -> None:
        np.save(self._path(key), array)
        self.evict()

    def size(self) -> int:
        return sum(p.stat().st_size for p in self.dir.glob("*.npy"))

    def evict(self) -> None:
        files = sorted(self.dir.glob("*.npy"), key=lambda p: p.stat().st_mtime)
        total = self.size()
        for path in files:
            if total <= self.max_bytes:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_cog.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/cog.py app/tests/test_cog.py
git commit -m "feat: utm grid, cog window read and lru cache"
```

---

## Task 9: SQLite-Schicht

**Files:**
- Create: `app/src/fieldwatch/db.py`
- Test: `app/tests/test_db.py`

**Interfaces:**
- Consumes: `sqlite3`
- Produces: `connect`, `init_db`, `create_field`, `list_fields`, `get_field`, `delete_field`, `save_observations`, `get_observations`, `save_demand`, `get_demand`, `log_source`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_db.py`:

```python
import pytest

from fieldwatch.db import (
    connect,
    create_field,
    delete_field,
    get_demand,
    get_field,
    get_observations,
    init_db,
    list_fields,
    log_source,
    save_demand,
    save_observations,
)

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "test.sqlite")
    init_db(connection)
    yield connection
    connection.close()


def test_create_and_get(conn):
    field_id = create_field(conn, "Acker Nord", SQUARE, 800_000.0, "NW")
    row = get_field(conn, field_id)
    assert row["name"] == "Acker Nord"
    assert row["area_m2"] == pytest.approx(800_000.0)
    assert row["geometry"]["type"] == "Polygon"


def test_list_and_delete(conn):
    first = create_field(conn, "A", SQUARE, 1.0, "NW")
    create_field(conn, "B", SQUARE, 2.0, "BY")
    assert [f["name"] for f in list_fields(conn)] == ["A", "B"]
    assert delete_field(conn, first) is True
    assert delete_field(conn, 9999) is False
    assert len(list_fields(conn)) == 1


def test_observations_replace(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    save_observations(conn, field_id, [
        {"date": "2026-01-01", "median_ndvi": 0.2, "mean_ndvi": 0.21,
         "clear_pct": 0.9, "pixels": 100, "frame": b"\x01\x02"},
    ])
    save_observations(conn, field_id, [
        {"date": "2026-02-01", "median_ndvi": 0.4, "mean_ndvi": 0.41,
         "clear_pct": 0.8, "pixels": 100, "frame": b"\x03"},
    ])
    rows = get_observations(conn, field_id)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-02-01"
    assert rows[0]["frame"] == b"\x03"


def test_demand_roundtrip(conn):
    field_id = create_field(conn, "A", SQUARE, 1.0, "NW")
    save_demand(conn, field_id, {"week_mm": 4.2, "week_m3": 3360.0, "stale_canopy": False})
    payload = get_demand(conn, field_id)
    assert payload["week_mm"] == pytest.approx(4.2)
    assert payload["stale_canopy"] is False


def test_source_log(conn):
    log_source(conn, "stac", "https://example", 200, 1234, 50, "Copernicus")
    assert conn.execute("SELECT COUNT(*) FROM source_log").fetchone()[0] == 1


def test_wal_mode(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.db'`

- [ ] **Step 3: `db.py` implementieren**

```python
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    geometry TEXT NOT NULL,
    area_m2 REAL NOT NULL,
    state TEXT NOT NULL DEFAULT 'none',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    median_ndvi REAL,
    mean_ndvi REAL,
    clear_pct REAL NOT NULL,
    pixels INTEGER NOT NULL,
    frame BLOB,
    frame_width INTEGER,
    frame_height INTEGER,
    PRIMARY KEY (field_id, date)
);
CREATE TABLE IF NOT EXISTS demand (
    field_id INTEGER PRIMARY KEY REFERENCES fields(id) ON DELETE CASCADE,
    payload TEXT NOT NULL,
    computed_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS source_log (
    ts INTEGER NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    status INTEGER NOT NULL,
    bytes INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    license TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def create_field(conn, name: str, geometry: dict, area: float, state: str) -> int:
    cur = conn.execute(
        "INSERT INTO fields (name, geometry, area_m2, state, created_at) VALUES (?,?,?,?,?)",
        (name, json.dumps(geometry), float(area), state, int(time.time())),
    )
    conn.commit()
    return int(cur.lastrowid)


def _field_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    data["geometry"] = json.loads(data["geometry"])
    return data


def list_fields(conn) -> list[dict]:
    return [_field_row(r) for r in conn.execute("SELECT * FROM fields ORDER BY id").fetchall()]


def get_field(conn, field_id: int) -> dict | None:
    return _field_row(conn.execute("SELECT * FROM fields WHERE id=?", (field_id,)).fetchone())


def delete_field(conn, field_id: int) -> bool:
    cur = conn.execute("DELETE FROM fields WHERE id=?", (field_id,))
    conn.commit()
    return cur.rowcount > 0


def save_observations(conn, field_id: int, rows: list[dict]) -> None:
    conn.execute("DELETE FROM observations WHERE field_id=?", (field_id,))
    conn.executemany(
        "INSERT INTO observations (field_id, date, median_ndvi, mean_ndvi, clear_pct, pixels, frame,"
        " frame_width, frame_height)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                field_id,
                row["date"],
                row.get("median_ndvi"),
                row.get("mean_ndvi"),
                float(row["clear_pct"]),
                int(row["pixels"]),
                row.get("frame"),
                row.get("frame_width"),
                row.get("frame_height"),
            )
            for row in rows
        ],
    )
    conn.commit()


def get_observations(conn, field_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM observations WHERE field_id=? ORDER BY date", (field_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def save_demand(conn, field_id: int, payload: dict) -> None:
    conn.execute(
        "INSERT INTO demand (field_id, payload, computed_at) VALUES (?,?,?)"
        " ON CONFLICT(field_id) DO UPDATE SET payload=excluded.payload, computed_at=excluded.computed_at",
        (field_id, json.dumps(payload), int(time.time())),
    )
    conn.commit()


def get_demand(conn, field_id: int) -> dict | None:
    row = conn.execute("SELECT payload FROM demand WHERE field_id=?", (field_id,)).fetchone()
    return None if row is None else json.loads(row["payload"])


def log_source(conn, source: str, url: str, status: int, bytes_: int, duration_ms: int, license_: str) -> None:
    conn.execute(
        "INSERT INTO source_log (ts, source, url, status, bytes, duration_ms, license)"
        " VALUES (?,?,?,?,?,?,?)",
        (int(time.time()), source, url, status, bytes_, duration_ms, license_),
    )
    conn.commit()
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/db.py app/tests/test_db.py
git commit -m "feat: sqlite persistence for fields, series and demand"
```

---

## Task 10: Modell und Pipeline

**Files:**
- Create: `app/src/fieldwatch/model.py`, `app/src/fieldwatch/pipeline.py`
- Test: `app/tests/test_model.py`, `app/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `indices`, `zonal`, `cog`, `stac`, `weather`, `geo`
- Produces:
  - `canopy_from_ndvi(ndvi: float) -> tuple[float, float]` → `(cc, kcb)`
  - `demand_from(kcb: float, eto: list[DailyEto | None], area_m2: float) -> dict` mit Keys `kcb`, `etc_mm`, `week_mm`, `week_m3`, `area_m2`, `complete`, `missing_days`
  - `AnalyseResult` dataclass: `observations: list[dict]`, `demand: dict`, `flags: list[str]`
  - `analyse_field(geometry, *, scenes, arrays_for, forecast, grid, min_clear_pct=0.70, stale_days=21, today=None) -> AnalyseResult`

- [ ] **Step 1: Failing Test für das Modell schreiben**

`app/tests/test_model.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_model.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.model'`

- [ ] **Step 3: `model.py` implementieren**

```python
from __future__ import annotations

from .weather import DailyEto

CC_MIN = 0.0
CC_MAX = 0.8


def canopy_from_ndvi(ndvi: float) -> tuple[float, float]:
    cc = 1.22 * float(ndvi) - 0.21
    cc = min(max(cc, CC_MIN), CC_MAX)
    kcb = 1.13 * cc + 0.14
    return cc, kcb


def demand_from(kcb: float, eto: list[DailyEto | None], area_m2: float) -> dict:
    etc: list[float | None] = []
    for day in eto:
        value = None if day is None else day.eto_mm
        etc.append(None if value is None else round(kcb * value, 3))
    valid = [v for v in etc if v is not None]
    week_mm = round(sum(valid), 3)
    missing = sum(1 for v in etc if v is None)
    return {
        "kcb": round(kcb, 4),
        "etc_mm": etc,
        "week_mm": week_mm,
        "week_m3": round(week_mm * float(area_m2) / 1000.0, 1),
        "area_m2": round(float(area_m2), 1),
        "complete": missing == 0 and len(etc) > 0,
        "missing_days": missing,
    }
```

- [ ] **Step 4: Modelltests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_model.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Failing Test für die Pipeline schreiben**

`app/tests/test_pipeline.py`:

```python
from datetime import date

import numpy as np
import pytest
from affine import Affine

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.pipeline import analyse_field
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}
GRID = make_grid((6.99, 50.99, 7.02, 51.02))


def _arrays(red=0.1, nir=0.5, scl=4):
    shape = (GRID.height, GRID.width)
    return SceneArrays(
        red=np.full(shape, red, dtype=np.float32),
        nir=np.full(shape, nir, dtype=np.float32),
        scl=np.full(shape, scl, dtype=np.float32),
    )


def _scene(day: str) -> SceneRef:
    return SceneRef(
        id=day,
        datetime=f"{day}T10:00:00Z",
        cloud_cover=0.0,
        hrefs={"red": "r", "nir": "n", "scl": "s"},
    )


def _forecast(n=7, value=2.0):
    return [DailyEto(f"2026-10-{20+i:02d}", value, 0.0) for i in range(n)]


def test_analyse_field_produces_observations_and_demand():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-09-01"), _scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert len(result.observations) == 2
    assert result.observations[0]["median_ndvi"] == pytest.approx(2 / 3, abs=1e-3)
    assert result.demand["week_mm"] > 0
    assert result.demand["complete"] is True
    assert "insufficient_pixels" not in result.flags


def test_all_cloudy_scene_is_skipped_with_flag():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(scl=8),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert result.observations == []
    assert "no_clear_observation" in result.flags
    assert result.demand["status"] == "unavailable"


def test_tiny_field_is_flagged():
    tiny = {
        "type": "Polygon",
        "coordinates": [[[7.0, 51.0], [7.00002, 51.0], [7.00002, 51.00002], [7.0, 51.00002], [7.0, 51.0]]],
    }
    result = analyse_field(
        tiny,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert "insufficient_pixels" in result.flags


def test_stale_canopy_flagged():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-06-01")],
        arrays_for=lambda s: _arrays(),
        forecast=_forecast(),
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert "stale_canopy" in result.flags


def test_missing_forecast_degrades():
    result = analyse_field(
        SQUARE,
        scenes=[_scene("2026-10-01")],
        arrays_for=lambda s: _arrays(),
        forecast=[DailyEto("2026-10-20", None, None)],
        grid=GRID,
        today=date(2026, 10, 20),
    )
    assert result.demand["complete"] is False
    assert result.demand["status"] == "unavailable"
```

- [ ] **Step 6: Pipeline-Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.pipeline'`

- [ ] **Step 7: `pipeline.py` implementieren**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import numpy as np

from .cog import Grid, SceneArrays
from .geo import area_m2
from .indices import clear_fraction, clear_mask, ndvi_array, to_uint8_frame
from .model import canopy_from_ndvi, demand_from
from .stac import SceneRef
from .weather import DailyEto
from .zonal import polygon_mask, zonal_stats


@dataclass
class AnalyseResult:
    observations: list[dict] = field(default_factory=list)
    demand: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _empty_demand(reason: str, forecast_size: int) -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "kcb": None,
        "etc_mm": [],
        "week_mm": None,
        "week_m3": None,
        "complete": False,
        "missing_days": forecast_size,
    }


def analyse_field(
    geometry: dict,
    *,
    scenes: list[SceneRef],
    arrays_for: Callable[[SceneRef], SceneArrays],
    forecast: list[DailyEto | None],
    grid: Grid,
    min_clear_pct: float = 0.70,
    stale_days: int = 21,
    today: date | None = None,
) -> AnalyseResult:
    today = today or date.today()
    result = AnalyseResult()
    inside = polygon_mask(grid.transform, (grid.height, grid.width), geometry)
    if not inside.any():
        result.flags.extend(["insufficient_pixels", "no_clear_observation"])
        result.demand = _empty_demand("insufficient_pixels", len(forecast))
        return result

    for scene in sorted(scenes, key=lambda s: s.datetime):
        arrays = arrays_for(scene)
        valid = np.isfinite(arrays.red) & np.isfinite(arrays.nir)
        ndvi = ndvi_array(arrays.red, arrays.nir)
        scl = np.nan_to_num(arrays.scl, nan=0).astype(np.uint8)
        clear = clear_mask(scl)
        if clear_fraction(clear, inside) < min_clear_pct:
            continue
        stats = zonal_stats(ndvi, valid & clear, inside, clear)
        if stats.median is None:
            continue
        if not stats.sufficient and "insufficient_pixels" not in result.flags:
            result.flags.append("insufficient_pixels")
        frame = to_uint8_frame(ndvi, valid & clear & inside)
        result.observations.append(
            {
                "date": _parse_date(scene.datetime).isoformat(),
                "median_ndvi": round(stats.median, 4),
                "mean_ndvi": round(stats.mean, 4) if stats.mean is not None else None,
                "clear_pct": round(stats.clear_pct, 4),
                "pixels": stats.pixels,
                "frame": frame.tobytes(),
                "frame_width": int(frame.shape[1]),
                "frame_height": int(frame.shape[0]),
            }
        )

    if not result.observations:
        result.flags.append("no_clear_observation")
        result.demand = _empty_demand("no_clear_observation", len(forecast))
        return result

    latest = result.observations[-1]
    age = (today - date.fromisoformat(latest["date"])).days
    if age > stale_days:
        result.flags.append("stale_canopy")

    cc, kcb = canopy_from_ndvi(latest["median_ndvi"])
    missing = sum(1 for day in forecast if day is None or day.eto_mm is None)
    demand = demand_from(kcb, forecast, area_m2(geometry))
    demand["cover"] = round(cc, 4)
    demand["canopy_date"] = latest["date"]
    demand["canopy_age_days"] = age
    if missing == 0:
        demand["status"] = "ok"
    elif missing < len(forecast):
        demand["status"] = "partial"
    else:
        demand["status"] = "unavailable"
    result.demand = demand
    return result
```

- [ ] **Step 8: Pipeline-Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: PASS (5 passed)

- [ ] **Step 9: Alle Tests**

Run: `cd app && .venv/bin/python -m pytest -q`
Expected: PASS (alle)

- [ ] **Step 10: Commit**

```bash
git add app/src/fieldwatch/model.py app/src/fieldwatch/pipeline.py app/tests/test_model.py app/tests/test_pipeline.py
git commit -m "feat: crop water demand model and pipeline orchestration"
```

---

## Task 11: FastAPI-Schicht

**Files:**
- Create: `app/src/fieldwatch/api.py`
- Test: `app/tests/test_api.py`

**Interfaces:**
- Consumes: `Settings`, `db`, `geo`, `__version__`
- Produces: `create_app(settings: Settings | None = None, *, conn=None, deps: dict | None = None) -> FastAPI` (keine Modul-Instanz; `app_factory` folgt in Task 16)
- `deps`-Keys: `"parcels"` (Objekt mit `.resolve(lon, lat, state)`), `"analyse"` (`Callable[[int], dict]`)

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_api.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldwatch.api import create_app
from fieldwatch.config import Settings
from fieldwatch.db import connect, init_db

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    conn = connect(tmp_path / "app.sqlite")
    init_db(conn)
    app = create_app(settings, conn=conn, deps={})
    with TestClient(app) as c:
        yield c
    conn.close()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "version" in body


def test_states_lists_all_16(client):
    r = client.get("/api/states")
    assert r.status_code == 200
    assert len(r.json()["states"]) == 16


def test_create_and_list_field(client):
    r = client.post("/api/fields", json={"name": "Test", "geometry": SQUARE})
    assert r.status_code == 201
    field_id = r.json()["id"]
    assert client.get(f"/api/fields/{field_id}").json()["name"] == "Test"
    assert len(client.get("/api/fields").json()["fields"]) == 1


def test_reject_invalid_polygon(client):
    r = client.post(
        "/api/fields",
        json={"name": "Bad", "geometry": {"type": "Point", "coordinates": [1, 2]}},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


def test_unknown_field_404(client):
    r = client.get("/api/fields/999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_demand_unavailable_without_run(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.get(f"/api/fields/{field_id}/demand")
    assert r.status_code == 200
    assert r.json()["status"] == "unavailable"


def test_frames_empty_before_run(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.get(f"/api/fields/{field_id}/frames")
    assert r.status_code == 200
    assert r.json()["frames"] == []


def test_resolve_without_parcels_returns_not_found(client):
    r = client.get("/api/resolve", params={"lat": 51.0, "lon": 7.0})
    assert r.status_code == 200
    assert r.json()["found"] is False


def test_refresh_without_runner_is_503(client):
    field_id = client.post("/api/fields", json={"name": "T", "geometry": SQUARE}).json()["id"]
    r = client.post(f"/api/fields/{field_id}/refresh")
    assert r.status_code == 503
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.api'`

- [ ] **Step 3: `data/states.json` anlegen**

```json
{
  "version": 1,
  "states": [
    {"code": "BW", "name": "Baden-Württemberg", "status": "pending"},
    {"code": "BY", "name": "Bayern", "status": "pending"},
    {"code": "BE", "name": "Berlin", "status": "fallback"},
    {"code": "BB", "name": "Brandenburg", "status": "pending"},
    {"code": "HB", "name": "Bremen", "status": "fallback"},
    {"code": "HH", "name": "Hamburg", "status": "fallback"},
    {"code": "HE", "name": "Hessen", "status": "pending"},
    {"code": "MV", "name": "Mecklenburg-Vorpommern", "status": "pending"},
    {"code": "NI", "name": "Niedersachsen", "status": "pending"},
    {"code": "NW", "name": "Nordrhein-Westfalen", "status": "pending"},
    {"code": "RP", "name": "Rheinland-Pfalz", "status": "pending"},
    {"code": "SL", "name": "Saarland", "status": "pending"},
    {"code": "SN", "name": "Sachsen", "status": "pending"},
    {"code": "ST", "name": "Sachsen-Anhalt", "status": "pending"},
    {"code": "SH", "name": "Schleswig-Holstein", "status": "pending"},
    {"code": "TH", "name": "Thüringen", "status": "pending"}
  ]
}
```

- [ ] **Step 4: `api.py` implementieren**

```python
from __future__ import annotations

import base64
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings, load_settings
from .db import (
    connect,
    create_field,
    delete_field,
    get_demand,
    get_field,
    get_observations,
    init_db,
    list_fields,
)
from .geo import area_m2, validate_polygon

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = Path(__file__).resolve().parents[2]
STATES_PATH = REPO_ROOT / "data" / "states.json"
WEB_DIST = APP_ROOT / "web" / "dist"


class FieldIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    geometry: dict


def _error(status: int, code: str, message: str, detail: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "detail": detail}},
    )


def _load_states() -> list[dict]:
    if not STATES_PATH.exists():
        return []
    return json.loads(STATES_PATH.read_text(encoding="utf-8"))["states"]


def _frame_payload(rows: list[dict]) -> dict:
    frames = []
    for row in rows:
        frame = row.get("frame")
        if not frame:
            continue
        width = row.get("frame_width") or 256
        height = row.get("frame_height") or 256
        frames.append(
            {
                "date": row["date"],
                "width": int(width),
                "height": int(height),
                "data": base64.b64encode(frame).decode("ascii"),
            }
        )
    return {"frames": frames}


def create_app(settings: Settings | None = None, *, conn=None, deps: dict | None = None) -> FastAPI:
    settings = settings or load_settings()
    deps = deps or {}
    own_conn = conn is None
    conn = conn or connect(settings.db_path)
    init_db(conn)

    api = FastAPI(
        title="FieldWatch",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    api.state.settings = settings
    api.state.conn = conn
    api.state.deps = deps

    @api.exception_handler(ValueError)
    async def _value_error(_request, exc: ValueError):
        return _error(422, "invalid_input", str(exc))

    @api.get("/healthz")
    def healthz():
        try:
            free = shutil.disk_usage(settings.data_dir).free
            disk_ok = free > 200 * 1024 * 1024
        except OSError:
            disk_ok = True
        return {
            "status": "ok" if disk_ok else "degraded",
            "version": __version__,
            "state": settings.state,
            "disk_ok": disk_ok,
            "db_ok": True,
        }

    @api.get("/api/states")
    def states():
        return {"states": _load_states()}

    @api.get("/api/resolve")
    def resolve(
        lat: float = Query(..., ge=-90, le=90),
        lon: float = Query(..., ge=-180, le=180),
    ):
        parcels = deps.get("parcels")
        if parcels is None:
            return {"found": False}
        hit = parcels.resolve(lon, lat, settings.state)
        if hit is None:
            return {"found": False}
        return {
            "found": True,
            "geometry": hit.geometry,
            "name": hit.name,
            "area_m2": hit.area_m2,
        }

    @api.post("/api/fields", status_code=201)
    def add_field(payload: FieldIn):
        validate_polygon(payload.geometry)
        field_id = create_field(
            conn,
            payload.name,
            payload.geometry,
            area_m2(payload.geometry),
            settings.state,
        )
        return {"id": field_id}

    @api.get("/api/fields")
    def fields():
        return {"fields": list_fields(conn)}

    @api.get("/api/fields/{field_id}")
    def field_detail(field_id: int):
        row = get_field(conn, field_id)
        if row is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return row

    @api.delete("/api/fields/{field_id}")
    def remove_field(field_id: int):
        if not delete_field(conn, field_id):
            return _error(404, "not_found", "Feld existiert nicht")
        return {"deleted": True}

    @api.get("/api/fields/{field_id}/series")
    def series(field_id: int, months: int = Query(12, ge=1, le=24)):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        cutoff = (date.today() - timedelta(days=int(months * 30.44))).isoformat()
        rows = [r for r in get_observations(conn, field_id) if r["date"] >= cutoff]
        return {
            "series": [
                {
                    "date": r["date"],
                    "median_ndvi": r["median_ndvi"],
                    "mean_ndvi": r["mean_ndvi"],
                    "clear_pct": r["clear_pct"],
                    "pixels": r["pixels"],
                }
                for r in rows
            ]
        }

    @api.get("/api/fields/{field_id}/frames")
    def frames(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return _frame_payload(get_observations(conn, field_id))

    @api.get("/api/fields/{field_id}/demand")
    def demand(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        return get_demand(conn, field_id) or {
            "status": "unavailable",
            "reason": "not_analysed",
            "kcb": None,
            "etc_mm": [],
            "week_mm": None,
            "week_m3": None,
            "complete": False,
            "missing_days": settings.forecast_days,
        }

    @api.post("/api/fields/{field_id}/refresh")
    def refresh(field_id: int):
        if get_field(conn, field_id) is None:
            return _error(404, "not_found", "Feld existiert nicht")
        runner = deps.get("analyse")
        if runner is None:
            return _error(503, "not_available", "Analyse ist nicht konfiguriert")
        return runner(field_id)

    if WEB_DIST.exists():
        api.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
    else:

        @api.get("/")
        def placeholder():
            return {"app": "fieldwatch", "ui": "not built"}

    return api
```

- [ ] **Step 5: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (9 passed)

- [ ] **Step 6: `httpx` für TestClient sicherstellen**

```bash
grep -q '^httpx==' app/requirements.txt || echo 'httpx==0.28.1' >> app/requirements.txt
```

- [ ] **Step 7: Commit**

```bash
git add app/src/fieldwatch/api.py app/tests/test_api.py data/states.json
git commit -m "feat: fastapi endpoints, healthz and static frontend mount"
```

---

## Task 12: CLI für Einzelfeld-Analyse

**Files:**
- Create: `app/src/fieldwatch/cli.py`
- Test: `app/tests/test_cli.py`

**Interfaces:**
- Consumes: `stac.search`, `cog.make_grid`/`read_scene`, `weather.fetch_forecast`, `pipeline.analyse_field`, `geo.square_around`
- Produces:
  - `build_runtime(settings) -> dict` mit `search`, `read_scene`, `forecast`
  - `run_point(lat, lon, radius_m, *, settings=None, runtime=None, today=None) -> dict`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_cli.py`:

```python
from datetime import date

import numpy as np
import pytest

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.cli import run_point
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

GRID = make_grid((6.99, 50.99, 7.02, 51.02))


def _runtime():
    shape = (GRID.height, GRID.width)
    return {
        "search": lambda geometry, months, max_cloud: [
            SceneRef("a", "2026-10-01T10:00:00Z", 0.0, {"red": "r", "nir": "n", "scl": "s"})
        ],
        "grid": lambda geometry: GRID,
        "arrays": lambda scene, geometry, grid: SceneArrays(
            red=np.full(shape, 0.1, dtype=np.float32),
            nir=np.full(shape, 0.4, dtype=np.float32),
            scl=np.full(shape, 4, dtype=np.float32),
        ),
        "forecast": lambda lat, lon, days: [DailyEto(f"2026-10-{20+i:02d}", 2.0, 0.0) for i in range(days)],
    }


def test_run_point_returns_series_and_demand():
    out = run_point(51.0, 7.0, 100.0, runtime=_runtime(), today=date(2026, 10, 20))
    assert out["geometry"]["type"] == "Polygon"
    assert len(out["observations"]) == 1
    assert out["demand"]["status"] == "ok"
    assert out["demand"]["week_mm"] > 0
    assert "frame" not in out["observations"][0]


def test_run_point_empty_search_degrades():
    runtime = _runtime()
    runtime["search"] = lambda geometry, months, max_cloud: []
    out = run_point(51.0, 7.0, 100.0, runtime=runtime, today=date(2026, 10, 20))
    assert out["observations"] == []
    assert out["demand"]["status"] == "unavailable"


def test_main_requires_lat_lon(capsys):
    from fieldwatch.cli import main

    code = main(["run"])
    assert code == 2
    assert "lat" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.cli'`

- [ ] **Step 3: `cli.py` implementieren**

```python
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .cog import make_grid, read_scene
from .config import Settings, load_settings
from .geo import bbox_of, buffer_bbox, square_around
from .pipeline import analyse_field
from .stac import search
from .weather import fetch_forecast


def build_runtime(settings: Settings) -> dict:
    return {
        "search": lambda geometry, months, max_cloud: search(
            geometry, months=months, max_cloud=max_cloud
        ),
        "grid": lambda geometry: make_grid(buffer_bbox(bbox_of(geometry), 0.10)),
        "arrays": lambda scene, geometry, grid: read_scene(scene, geometry, grid),
        "forecast": lambda lat, lon, days: fetch_forecast(lat, lon, days=days),
    }


def run_point(
    lat: float,
    lon: float,
    radius_m: float,
    *,
    settings: Settings | None = None,
    runtime: dict | None = None,
    today: date | None = None,
) -> dict:
    settings = settings or load_settings()
    runtime = runtime or build_runtime(settings)
    geometry = square_around(lon, lat, radius_m)
    grid = runtime["grid"](geometry)
    scenes = runtime["search"](geometry, settings.history_months, settings.max_cloud_cover)
    forecast = runtime["forecast"](lat, lon, settings.forecast_days)
    result = analyse_field(
        geometry,
        scenes=scenes,
        arrays_for=lambda scene: runtime["arrays"](scene, geometry, grid),
        forecast=forecast,
        grid=grid,
        min_clear_pct=settings.min_clear_pct,
        stale_days=settings.stale_days,
        today=today,
    )
    return {
        "geometry": geometry,
        "observations": [
            {k: v for k, v in obs.items() if k != "frame"} for obs in result.observations
        ],
        "demand": result.demand,
        "flags": result.flags,
        "scenes_found": len(scenes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fieldwatch")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Ein Feld um einen Punkt analysieren")
    run.add_argument("--lat", type=float, required=True)
    run.add_argument("--lon", type=float, required=True)
    run.add_argument("--radius", type=float, default=100.0, help="Halbkante in Metern")
    run.add_argument("--out", type=Path, default=None)

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.command != "run":
        parser.error("unbekannter Befehl")    if args.lat is None or args.lon is None:
        print("Fehler: --lat und --lon sind erforderlich", file=sys.stderr)
        return 2

    payload = run_point(args.lat, args.lon, args.radius)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"geschrieben: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/cli.py app/tests/test_cli.py
git commit -m "feat: cli for single-field analysis"
```

---

## Task 13: Feldblock-Index mit Fallback

**Files:**
- Create: `app/src/fieldwatch/parcels.py`
- Test: `app/tests/test_parcels.py`

**Interfaces:**
- Consumes: `fiona`, `shapely`, `geo`
- Produces:
  - `Parcel` dataclass: `name: str`, `geometry: dict`, `area_m2: float`
  - `ParcelIndex(parcel_dir: Path)` mit `.available_states() -> list[str]` und `.resolve(lon, lat, state) -> Parcel | None`
  - `import_file(source: Path, state: str, parcel_dir: Path) -> int`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_parcels.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_parcels.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.parcels'`

- [ ] **Step 3: `parcels.py` implementieren**

```python
from __future__ import annotations

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
    tmp = target.with_suffix(".fgb.part")
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
                    geo = mapping(geom)
                    return Parcel(
                        name=str(props.get("name") or props.get("FLIK") or "Feld"),
                        geometry=dict(geo),
                        area_m2=area_m2(dict(geo)),
                    )
        return None
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_parcels.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/parcels.py app/tests/test_parcels.py
git commit -m "feat: flatgeobuf parcel index with import"
```

---

## Task 14: Scheduler und laufende Analyse

**Files:**
- Create: `app/src/fieldwatch/runtime.py`, `app/src/fieldwatch/scheduler.py`
- Test: `app/tests/test_runtime.py`

**Interfaces:**
- Consumes: `stac`, `cog`, `weather`, `pipeline`, `db`, `parcels`
- Produces:
  - `analyse_field_by_id(field_id: int, *, settings, conn, cache) -> dict` (speichert Serie + Demand in DB)
  - `build_deps(settings, conn, cache) -> dict` (`{"parcels", "analyse"}` für `create_app`)
  - `start_scheduler(settings, conn, cache) -> BackgroundScheduler | None`

- [ ] **Step 1: Failing Test schreiben**

`app/tests/test_runtime.py`:

```python
from datetime import date

import numpy as np
import pytest

from fieldwatch.cog import Grid, SceneArrays, make_grid
from fieldwatch.config import Settings
from fieldwatch.db import connect, create_field, get_demand, get_observations, init_db
from fieldwatch.runtime import analyse_field_by_id
from fieldwatch.stac import SceneRef
from fieldwatch.weather import DailyEto

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[7.0, 51.0], [7.01, 51.0], [7.01, 51.01], [7.0, 51.01], [7.0, 51.0]]],
}
GRID = make_grid((6.99, 50.99, 7.02, 51.02))


class FakeCache:
    def get(self, key):
        return None

    def put(self, key, value):
        pass


@pytest.fixture()
def conn(tmp_path):
    connection = connect(tmp_path / "db.sqlite")
    init_db(connection)
    yield connection
    connection.close()


def _clients():
    shape = (GRID.height, GRID.width)
    return {
        "search": lambda geometry, months, max_cloud: [
            SceneRef("s1", "2026-10-01T10:00:00Z", 0.0, {"red": "r", "nir": "n", "scl": "s"})
        ],
        "grid": lambda geometry: GRID,
        "arrays": lambda scene, geometry, grid: SceneArrays(
            red=np.full(shape, 0.1, dtype=np.float32),
            nir=np.full(shape, 0.5, dtype=np.float32),
            scl=np.full(shape, 4, dtype=np.float32),
        ),
        "forecast": lambda lat, lon, days: [DailyEto(f"2026-10-{20+i:02d}", 2.0, 0.0) for i in range(days)],
    }


def test_analyse_field_by_id_persists(conn, tmp_path):
    settings = Settings(data_dir=tmp_path)
    field_id = create_field(conn, "A", SQUARE, 800_000.0, "NW")
    result = analyse_field_by_id(
        field_id, settings=settings, conn=conn, cache=FakeCache(),
        clients=_clients(), today=date(2026, 10, 20)
    )
    assert result["demand"]["status"] == "ok"
    assert len(get_observations(conn, field_id)) == 1
    assert get_demand(conn, field_id)["week_mm"] > 0


def test_analyse_unknown_field_raises(conn, tmp_path):
    settings = Settings(data_dir=tmp_path)
    with pytest.raises(KeyError):
        analyse_field_by_id(999, settings=settings, conn=conn, cache=FakeCache(), clients=_clients())
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_runtime.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fieldwatch.runtime'`

- [ ] **Step 3: `runtime.py` implementieren**

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from .cog import CogCache, make_grid, read_scene
from .config import Settings
from .db import get_field, log_source, save_demand, save_observations
from .geo import bbox_of, buffer_bbox, centroid
from .parcels import ParcelIndex
from .pipeline import analyse_field
from .stac import search
from .weather import fetch_forecast

CACHE_KEY = "{scene_id}:{asset}:{grid_crs}:{grid_w}x{grid_h}"


def _default_clients(settings: Settings, cache: CogCache) -> dict:
    def _grid(geometry):
        return make_grid(buffer_bbox(bbox_of(geometry), 0.10))

    def _arrays(scene, geometry, grid):
        return read_scene(scene, geometry, grid)

    return {
        "search": lambda geometry, months, max_cloud: search(
            geometry, months=months, max_cloud=max_cloud
        ),
        "grid": _grid,
        "arrays": _arrays,
        "forecast": lambda lat, lon, days: fetch_forecast(lat, lon, days=days),
    }


def analyse_field_by_id(
    field_id: int,
    *,
    settings: Settings,
    conn,
    cache,
    clients: dict | None = None,
    today: date | None = None,
) -> dict:
    field = get_field(conn, field_id)
    if field is None:
        raise KeyError(f"Feld {field_id} existiert nicht")

    clients = clients or _default_clients(settings, cache)
    geometry = field["geometry"]
    grid = clients["grid"](geometry)
    scenes = clients["search"](geometry, settings.history_months, settings.max_cloud_cover)
    lon, lat = centroid(geometry)
    forecast = clients["forecast"](lat, lon, settings.forecast_days)

    result = analyse_field(
        geometry,
        scenes=scenes,
        arrays_for=lambda scene: clients["arrays"](scene, geometry, grid),
        forecast=forecast,
        grid=grid,
        min_clear_pct=settings.min_clear_pct,
        stale_days=settings.stale_days,
        today=today,
    )

    save_observations(conn, field_id, result.observations)
    save_demand(conn, field_id, {**result.demand, "flags": result.flags})
    log_source(
        conn,
        "stac",
        "https://earth-search.aws.element84.com/v1/search",
        200,
        len(scenes),
        0,
        "Copernicus",
    )
    return {"demand": result.demand, "flags": result.flags, "observations": len(result.observations)}


def build_deps(settings: Settings, conn, cache=None) -> dict:
    cache = cache or CogCache(settings.cache_dir, settings.cache_max_bytes)
    return {
        "parcels": ParcelIndex(settings.parcel_dir),
        "analyse": lambda field_id: analyse_field_by_id(
            field_id, settings=settings, conn=conn, cache=cache
        ),
    }
```

- [ ] **Step 4: `scheduler.py` implementieren**

```python
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
```

- [ ] **Step 5: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_runtime.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add app/src/fieldwatch/runtime.py app/src/fieldwatch/scheduler.py app/tests/test_runtime.py
git commit -m "feat: runtime wiring and periodic refresh"
```

---

## Task 15: Frontend-Gerüst und Frame-Logik

**Files:**
- Create: `app/web/package.json`, `app/web/tsconfig.json`, `app/web/vite.config.ts`, `app/web/index.html`, `app/web/src/main.tsx`, `app/web/src/frames.ts`, `app/web/src/frames.test.ts`, `app/web/src/styles.css`
- Modify: `app/src/fieldwatch/api.py` (Endpoint `/api/config`)

**Interfaces:**
- Consumes: nichts
- Produces:
  - `Frame` Interface `{date, width, height, data}`
  - `decodeFrame(frame: Frame): Uint8Array`
  - `interpolate(a: Uint8Array, b: Uint8Array, t: number): Uint8Array`
  - `ramp(value: number): [number, number, number]` (`value` 0–255)
  - `positionFor(frames: Frame[], index: number, t: number): string` (ISO-Datum)
  - `/api/config` → `{basemap, state, attribution}`

- [ ] **Step 1: `package.json` schreiben**

```json
{
  "name": "fieldwatch-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "maplibre-gl": "4.7.1",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "@types/geojson": "7946.0.16",
    "@vitejs/plugin-react": "4.3.4",
    "typescript": "5.7.2",
    "vite": "6.0.7",
    "vitest": "2.1.8"
  }
}
```

- [ ] **Step 2: `vite.config.ts`, `tsconfig.json`, `index.html` schreiben**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: { "/api": "http://127.0.0.1:8080", "/healthz": "http://127.0.0.1:8080" },
  },
});
```

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "noEmit": true,
    "types": ["vitest/globals", "geojson"]
  },
  "include": ["src"]
}
```

```html
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>FieldWatch</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Failing Test für `frames.ts` schreiben**

`app/web/src/frames.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { decodeFrame, interpolate, positionFor, ramp } from "./frames";

function frame(width: number, height: number, values: number[]) {
  return { date: "2026-01-01", width, height, data: btoa(String.fromCharCode(...values)) };
}

describe("frames", () => {
  it("decodes base64 into bytes", () => {
    const bytes = decodeFrame(frame(2, 1, [0, 128]));
    expect(Array.from(bytes)).toEqual([0, 128]);
  });

  it("interpolates linearly and keeps nodata", () => {
    const a = new Uint8Array([0, 100, 200]);
    const b = new Uint8Array([100, 200, 0]);
    expect(Array.from(interpolate(a, b, 0.5))).toEqual([50, 150, 0]);
    expect(Array.from(interpolate(a, b, 0))).toEqual([0, 100, 0]);
    expect(Array.from(interpolate(a, b, 1))).toEqual([100, 200, 0]);
  });

  it("maps values to a green ramp", () => {
    expect(ramp(0)[3]).toBe(0);
    expect(ramp(64)[1]).toBeLessThan(ramp(200)[1]);
  });

  it("positions a date between two frames", () => {
    const frames = [
      { date: "2026-01-01", width: 1, height: 1, data: "" },
      { date: "2026-03-01", width: 1, height: 1, data: "" },
    ];
    expect(positionFor(frames, 0, 0.5)).toBe("2026-01-30");
    expect(positionFor(frames, 1, 0)).toBe("2026-03-01");
  });
});
```

- [ ] **Step 4: Test laufen lassen (FAIL)**

Run: `cd app/web && npm install && npm test`
Expected: FAIL, `Cannot find module './frames'`

- [ ] **Step 5: `frames.ts` implementieren**

```ts
export interface Frame {
  date: string;
  width: number;
  height: number;
  data: string;
}

export function decodeFrame(frame: Frame): Uint8Array {
  const binary = atob(frame.data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function interpolate(a: Uint8Array, b: Uint8Array, t: number): Uint8Array {
  const out = new Uint8Array(a.length);
  const clamped = Math.min(Math.max(t, 0), 1);
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] === 0 || b[i] === 0) {
      out[i] = 0;
      continue;
    }
    out[i] = Math.round(a[i] + (b[i] - a[i]) * clamped);
  }
  return out;
}

const STOPS: Array<[number, [number, number, number, number]]> = [
  [0, [0, 0, 0, 0]],
  [1, [120, 90, 60, 255]],
  [64, [190, 175, 120, 255]],
  [128, [150, 190, 90, 255]],
  [192, [40, 140, 60, 255]],
  [255, [10, 80, 30, 255]],
];

export function ramp(value: number): [number, number, number, number] {
  for (let i = 1; i < STOPS.length; i += 1) {
    const [hi, high] = STOPS[i];
    const [lo, low] = STOPS[i - 1];
    if (value <= hi) {
      const f = (value - lo) / (hi - lo);
      return [
        Math.round(low[0] + (high[0] - low[0]) * f),
        Math.round(low[1] + (high[1] - low[1]) * f),
        Math.round(low[2] + (high[2] - low[2]) * f),
        Math.round(low[3] + (high[3] - low[3]) * f),
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

export function positionFor(frames: Frame[], index: number, t: number): string {
  if (frames.length === 0) return "";
  const current = frames[Math.min(index, frames.length - 1)];
  if (index >= frames.length - 1) return current.date;
  const next = frames[index + 1];
  const start = Date.parse(current.date);
  const end = Date.parse(next.date);
  return new Date(start + (end - start) * Math.min(Math.max(t, 0), 1))
    .toISOString()
    .slice(0, 10);
}
```

- [ ] **Step 6: Tests grün**

Run: `cd app/web && npm test`
Expected: PASS (4 passed)

- [ ] **Step 7: `main.tsx` und `styles.css` schreiben**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```css
:root {
  --bg: #0f1210;
  --panel: #171c19;
  --line: #2a332d;
  --text: #e6efe8;
  --muted: #8fa294;
  --accent: #7fd48b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.app { display: flex; flex-direction: column; height: 100vh; }
header { padding: 12px 16px; border-bottom: 1px solid var(--line); display: flex; gap: 12px; align-items: center; }
main { flex: 1; display: grid; grid-template-columns: 1fr 340px; min-height: 0; }
.map { position: relative; min-height: 0; }
.side { border-left: 1px solid var(--line); padding: 16px; overflow: auto; background: var(--panel); }
.timeline { border-top: 1px solid var(--line); padding: 12px 16px; background: var(--panel); }
button {
  background: var(--accent); color: #07120a; border: 0; border-radius: 6px;
  padding: 8px 14px; font-weight: 600; cursor: pointer;
}
button.ghost { background: transparent; color: var(--text); border: 1px solid var(--line); }
.muted { color: var(--muted); font-size: 13px; }
.big { font-size: 28px; font-weight: 700; }
.flag { color: #f0b45a; font-size: 13px; }
footer { padding: 10px 16px; border-top: 1px solid var(--line); font-size: 12px; color: var(--muted); }
@media (max-width: 820px) {
  main { grid-template-columns: 1fr; grid-template-rows: 45vh auto; }
  .side { border-left: 0; border-top: 1px solid var(--line); }
}
```

- [ ] **Step 8: `/api/config` ergänzen**

In `app/src/fieldwatch/api.py` vor `if WEB_DIST.exists():` einfügen:

```python
    @api.get("/api/config")
    def config():
        return {
            "basemap": settings.basemap,
            "state": settings.state,
            "attribution": [
                "Contains modified Copernicus Sentinel data",
                "Weather data by Open-Meteo.com (CC BY 4.0)",
            ],
        }
```

- [ ] **Step 9: Frontend bauen und einchecken**

```bash
cd app/web && npm run build && cd ../..
git add app/web/package.json app/web/tsconfig.json app/web/vite.config.ts app/web/index.html app/web/src app/web/dist app/src/fieldwatch/api.py
git commit -m "feat: frontend scaffold and frame interpolation"
```

---

## Task 16: App-Factory und API-Verdrahtung

**Files:**
- Modify: `app/src/fieldwatch/api.py` (Factory)
- Test: `app/tests/test_api.py` (ergänzen)

**Interfaces:**
- Consumes: `runtime.build_deps`, `scheduler.start_scheduler`
- Produces: `app_factory() -> FastAPI` (uvicorn `--factory`)

- [ ] **Step 1: Failing Test schreiben**

```python
def test_factory_exposes_full_deps(monkeypatch, tmp_path):
    from fieldwatch.api import app_factory

    monkeypatch.setenv("FIELDWATCH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FIELDWATCH_SCHEDULER", "0")
    app = app_factory()
    with TestClient(app) as c:
        assert c.get("/api/config").json()["basemap"] in {"local", "osm"}
        assert c.get("/healthz").status_code == 200
```

- [ ] **Step 2: Test laufen lassen (FAIL)**

Run: `cd app && .venv/bin/python -m pytest tests/test_api.py::test_factory_exposes_full_deps -v`
Expected: FAIL, `ImportError: cannot import name 'app_factory'`

- [ ] **Step 3: Factory ergänzen**

Am Ende von `app/src/fieldwatch/api.py`:

```python
def app_factory() -> FastAPI:
    from .cog import CogCache
    from .runtime import build_deps
    from .scheduler import start_scheduler

    settings = load_settings()
    conn = connect(settings.db_path)
    cache = CogCache(settings.cache_dir, settings.cache_max_bytes)
    instance = create_app(settings, conn=conn, deps=build_deps(settings, conn, cache))
    instance.state.scheduler = start_scheduler(settings, conn, cache)
    return instance
```

- [ ] **Step 4: Tests grün**

Run: `cd app && .venv/bin/python -m pytest tests/test_api.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add app/src/fieldwatch/api.py app/tests/test_api.py
git commit -m "feat: app factory wiring deps and scheduler"
```

---

## Task 17: Karte, Feldauswahl und Zeichnen

**Files:**
- Create: `app/web/src/api.ts`, `app/web/src/Map.tsx`, `app/web/src/App.tsx`

**Interfaces:**
- Consumes: `/api/states`, `/api/resolve`, `/api/fields`, `/api/config`
- Produces: `App` default export; `Map` mit Props `{basemap, geometry, onPoint, onPolygon}`

- [ ] **Step 1: `api.ts` schreiben**

```ts
export interface FieldSummary {
  id: number;
  name: string;
  area_m2: number;
  state: string;
  geometry: { type: string; coordinates: unknown };
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => json<{ basemap: string; state: string; attribution: string[] }>("/api/config"),
  states: () => json<{ states: Array<{ code: string; name: string; status: string }> }>("/api/states"),
  fields: () => json<{ fields: FieldSummary[] }>("/api/fields"),
  field: (id: number) => json<FieldSummary>(`/api/fields/${id}`),
  frames: (id: number) =>
    json<{ frames: Array<{ date: string; width: number; height: number; data: string }> }>(
      `/api/fields/${id}/frames`
    ),
  demand: (id: number) => json<Record<string, unknown>>(`/api/fields/${id}/demand`),
  series: (id: number) =>
    json<{ series: Array<{ date: string; median_ndvi: number | null; clear_pct: number }> }>(
      `/api/fields/${id}/series`
    ),
  resolve: (lat: number, lon: number) =>
    json<{ found: boolean; geometry?: unknown; name?: string }>(
      `/api/resolve?lat=${lat}&lon=${lon}`
    ),
  create: (name: string, geometry: unknown) =>
    json<{ id: number }>("/api/fields", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, geometry }),
    }),
  refresh: (id: number) => json<Record<string, unknown>>(`/api/fields/${id}/refresh`, { method: "POST" }),
};
```

- [ ] **Step 2: `Map.tsx` schreiben**

```tsx
import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface Props {
  basemap: string;
  geometry: GeoJSON.Polygon | null;
  onPoint: (lon: number, lat: number) => void;
  onPolygon: (geometry: GeoJSON.Polygon) => void;
}

const EMPTY = { type: "FeatureCollection", features: [] } as const;

export default function Map({ basemap, geometry, onPoint, onPolygon }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [drawing, setDrawing] = useState(false);
  const points = useRef<[number, number][]>([]);

  useEffect(() => {
    if (!container.current || map.current) return;
    const style =
      basemap === "osm"
        ? {
            version: 8 as const,
            sources: {
              osm: {
                type: "raster" as const,
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap-Mitwirkende",
              },
            },
            layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
          }
        : { version: 8 as const, sources: {}, layers: [] };

    const instance = new maplibregl.Map({
      container: container.current,
      style,
      center: [10.0, 51.2],
      zoom: 5.4,
    });
    instance.addControl(new maplibregl.NavigationControl(), "top-left");
    instance.on("load", () => {
      instance.addSource("field", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "field-fill", type: "fill", source: "field",
        paint: { "fill-color": "#7fd48b", "fill-opacity": 0.18 } });
      instance.addLayer({ id: "field-line", type: "line", source: "field",
        paint: { "line-color": "#7fd48b", "line-width": 2 } });
      instance.addSource("draft", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "draft-line", type: "line", source: "draft",
        paint: { "line-color": "#f0b45a", "line-width": 2 } });
    });
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, [basemap]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !instance.getSource("field")) return;
    (instance.getSource("field") as maplibregl.GeoJSONSource).setData(
      geometry ? { type: "Feature", properties: {}, geometry } : EMPTY
    );
  }, [geometry]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const handler = (event: maplibregl.MapMouseEvent) => {
      const [lon, lat] = [event.lngLat.lng, event.lngLat.lat];
      if (!drawing) { onPoint(lon, lat); return; }
      points.current.push([lon, lat]);
      const ring = points.current;
      const draft = {
        type: "Feature" as const,
        properties: {},
        geometry: ring.length > 1
          ? { type: "LineString" as const, coordinates: ring }
          : { type: "Point" as const, coordinates: ring[0] },
      };
      (instance.getSource("draft") as maplibregl.GeoJSONSource).setData(draft as never);
      if (ring.length >= 3) {
        const closed = [...ring, ring[0]];
        onPolygon({ type: "Polygon", coordinates: [closed] });
      }
    };
    instance.on("click", handler);
    return () => { instance.off("click", handler); };
  }, [drawing, onPoint, onPolygon]);

  return (
    <div className="map">
      <div ref={container} style={{ position: "absolute", inset: 0 }} />
      <button
        className="ghost"
        style={{ position: "absolute", top: 12, right: 12, zIndex: 2 }}
        onClick={() => { points.current = []; setDrawing((d) => !d); }}
      >
        {drawing ? "Zeichnen beenden" : "Feld zeichnen"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: `App.tsx` schreiben**

```tsx
import { useCallback, useEffect, useState } from "react";
import { api, FieldSummary } from "./api";
import Map from "./Map";

export default function App() {
  const [config, setConfig] = useState({ basemap: "local", state: "none", attribution: [] as string[] });
  const [fields, setFields] = useState<FieldSummary[]>([]);
  const [selected, setSelected] = useState<FieldSummary | null>(null);
  const [draft, setDraft] = useState<GeoJSON.Polygon | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.config().then(setConfig).catch((e) => setError(String(e)));
    api.fields().then((r) => setFields(r.fields)).catch((e) => setError(String(e)));
  }, []);

  const pick = useCallback(async (lon: number, lat: number) => {
    setError("");
    try {
      const hit = await api.resolve(lat, lon);
      if (hit.found && hit.geometry) {
        setDraft(hit.geometry as GeoJSON.Polygon);
      }
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const save = async () => {
    if (!draft) return;
    const name = window.prompt("Feldname", "Feld") ?? "Feld";
    try {
      const { id } = await api.create(name, draft);
      const list = await api.fields();
      setFields(list.fields);
      setSelected(list.fields.find((f) => f.id === id) ?? null);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="app">
      <header>
        <strong>FieldWatch</strong>
        <span className="muted">{config.state === "none" ? "kein Bundesland" : config.state}</span>
        <button onClick={save} disabled={!draft}>Feld speichern</button>
      </header>
      <main>
        <Map
          basemap={config.basemap}
          geometry={draft ?? (selected?.geometry as GeoJSON.Polygon | undefined) ?? null}
          onPoint={pick}
          onPolygon={setDraft}
        />
        <aside className="side">
          <h3>Felder</h3>
          {fields.length === 0 && <p className="muted">Noch kein Feld. Auf die Karte tippen oder zeichnen.</p>}
          <ul>
            {fields.map((f) => (
              <li key={f.id}>
                <button className="ghost" onClick={() => { setSelected(f); setDraft(f.geometry as GeoJSON.Polygon); }}>
                  {f.name}
                </button>
                <span className="muted"> {Math.round(f.area_m2 / 10000)} ha</span>
              </li>
            ))}
          </ul>
          {error && <p className="flag">{error}</p>}
        </aside>
      </main>
      <footer>{config.attribution.join(" · ")}</footer>
    </div>
  );
}
```

- [ ] **Step 4: Build prüfen**

Run: `cd app/web && npm run build`
Expected: `dist/` entsteht ohne TypeScript-Fehler.

- [ ] **Step 5: Commit**

```bash
git add app/web/src app/web/dist
git commit -m "feat: map with field pick and polygon drawing"
```

---

## Task 18: Zeitachse, Wasser-Panel und Methodenseite

**Files:**
- Create: `app/web/src/Timeline.tsx`, `app/web/src/Demand.tsx`, `app/web/src/Method.tsx`
- Modify: `app/web/src/App.tsx`

**Interfaces:**
- Consumes: `api.frames`, `api.demand`, `frames.ts`
- Produces: Komponenten `Timeline({frames, index, t, onChange})`, `Demand({payload})`, `Method()`

- [ ] **Step 1: `Timeline.tsx` schreiben**

```tsx
import { useEffect, useRef } from "react";
import { Frame, decodeFrame, interpolate, ramp } from "./frames";

interface Props {
  frames: Frame[];
  index: number;
  t: number;
  onChange: (index: number, t: number) => void;
  playing: boolean;
  onToggle: () => void;
}

export default function Timeline({ frames, index, t, onChange, playing, onToggle }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el || frames.length === 0) return;
    const current = frames[Math.min(index, frames.length - 1)];
    const next = frames[Math.min(index + 1, frames.length - 1)];
    const a = decodeFrame(current);
    const b = decodeFrame(next);
    const pixels = interpolate(a, b, t);
    const ctx = el.getContext("2d");
    if (!ctx) return;
    el.width = current.width;
    el.height = current.height;
    const image = ctx.createImageData(current.width, current.height);
    for (let i = 0; i < pixels.length; i += 1) {
      const [r, g, bl, al] = ramp(pixels[i]);
      image.data[i * 4] = r;
      image.data[i * 4 + 1] = g;
      image.data[i * 4 + 2] = bl;
      image.data[i * 4 + 3] = al;
    }
    ctx.putImageData(image, 0, 0);
  }, [frames, index, t]);

  if (frames.length === 0) {
    return <div className="timeline muted">Noch keine Aufnahmen. „Analysieren" starten.</div>;
  }

  return (
    <div className="timeline">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <button onClick={onToggle}>{playing ? "Pause" : "Play"}</button>
        <canvas ref={canvas} style={{ width: 160, height: 160, imageRendering: "pixelated", borderRadius: 6 }} />
        <div>
          <div className="big">{frames[Math.min(index, frames.length - 1)].date}</div>
          <div className="muted">{frames.length} Aufnahmen</div>
        </div>
        <input
          type="range"
          min={0}
          max={Math.max(frames.length - 1, 0)}
          step={0.05}
          value={index + t}
          style={{ flex: 1 }}
          onChange={(e) => {
            const v = Number(e.target.value);
            onChange(Math.floor(v), v - Math.floor(v));
          }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `Demand.tsx` und `Method.tsx` schreiben**

```tsx
interface Props {
  payload: Record<string, unknown>;
}

export default function Demand({ payload }: Props) {
  const etc = (payload.etc_mm as Array<number | null> | undefined) ?? [];
  const weekMm = payload.week_mm as number | null | undefined;
  const weekM3 = payload.week_m3 as number | null | undefined;
  const status = (payload.status as string) ?? "unavailable";
  const flags = (payload.flags as string[] | undefined) ?? [];

  return (
    <section>
      <h3>Wasserbedarf 7 Tage</h3>
      {status === "unavailable" ? (
        <p className="muted">
          Keine belastbare Berechnung{payload.reason ? ` (${String(payload.reason)})` : ""}.
        </p>
      ) : (
        <>
          <div className="big">{weekMm?.toFixed(1)} mm</div>
          <div className="muted">{weekM3?.toFixed(0)} m³ · Kcb {String(payload.kcb ?? "–")}</div>
          <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginTop: 12 }}>
            {etc.map((v, i) => (
              <div
                key={i}
                title={`Tag ${i + 1}: ${v ?? "–"} mm`}
                style={{
                  flex: 1,
                  height: `${Math.min(100, ((v ?? 0) / Math.max(1, ...etc.map((x) => x ?? 0))) * 100)}%`,
                  background: v === null ? "#4a2f2f" : "var(--accent)",
                  borderRadius: 3,
                }}
              />
            ))}
          </div>
        </>
      )}
      <p className="muted">
        Bedarf, kein Verbrauch. Regen wird angezeigt, aber nicht abgezogen.
      </p>
      {flags.length > 0 && <p className="flag">Hinweise: {flags.join(", ")}</p>}
    </section>
  );
}
```

```tsx
export default function Method() {
  return (
    <section>
      <h3>Methode</h3>
      <p className="muted">
        NDVI aus Sentinel-2 L2A (B04/B08, 10 m), Wolkenmaske über das SCL-Band.
        Frames zwischen Überflügen linear interpoliert.
      </p>
      <pre style={{ fontSize: 12, overflowX: "auto" }}>
{`CC   = clip(1.22 · NDVI − 0.21, 0, 0.8)
Kcb  = 1.13 · CC + 0.14
ETc  = Kcb · ETo
m³   = mm · Fläche / 1000`}
      </pre>
      <p className="muted">
        Kalibriert für grüne Blätter und CC ≤ 0,8 (Trout &amp; Johnson 2007).
        Unbewachsener Boden, Netze und Beschattung unterschätzen den Bedarf.
        Das Ergebnis ist keine Bewässerungsanweisung.
      </p>
      <p className="muted">
        Quellen: Copernicus Sentinel-2, Open-Meteo (CC BY 4.0).
      </p>
    </section>
  );
}
```

- [ ] **Step 3: `App.tsx` erweitern**

Ersetze den `aside`-Block durch:

```tsx
        <aside className="side">
          <h3>Felder</h3>
          {fields.length === 0 && <p className="muted">Noch kein Feld. Auf die Karte tippen oder zeichnen.</p>}
          <ul>
            {fields.map((f) => (
              <li key={f.id}>
                <button className="ghost" onClick={() => select(f)}>
                  {f.name}
                </button>
                <span className="muted"> {Math.round(f.area_m2 / 10000)} ha</span>
              </li>
            ))}
          </ul>
          {selected && <Demand payload={demand} />}
          <Method />
          {error && <p className="flag">{error}</p>}
        </aside>
```

und ergänze oberhalb des `return`:

```tsx
  const [frames, setFrames] = useState<Frame[]>([]);
  const [demand, setDemand] = useState<Record<string, unknown>>({ status: "unavailable" });
  const [index, setIndex] = useState(0);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);

  const select = async (f: FieldSummary) => {
    setSelected(f);
    setDraft(f.geometry as GeoJSON.Polygon);
    const [fr, dm] = await Promise.all([api.frames(f.id), api.demand(f.id)]);
    setFrames(fr.frames);
    setDemand(dm);
    setIndex(0);
    setT(0);
  };

  useEffect(() => {
    if (!playing || frames.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex((i) => {
        const next = i + 1;
        if (next >= frames.length - 1) {
          setT(0);
          return frames.length - 1;
        }
        return next;
      });
      setT((v) => (v >= 0.95 ? 0 : v + 0.05));
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing, frames.length]);
```

und unter `main`:

```tsx
      <Timeline
        frames={frames}
        index={index}
        t={t}
        onChange={(i, tt) => { setIndex(i); setT(tt); }}
        playing={playing}
        onToggle={() => setPlaying((p) => !p)}
      />
```

Imports ergänzen: `import Timeline from "./Timeline"; import Demand from "./Demand"; import Method from "./Method"; import { Frame } from "./frames";`

- [ ] **Step 4: Build prüfen**

Run: `cd app/web && npm run build`
Expected: keine TypeScript-Fehler, `dist/` aktualisiert.

- [ ] **Step 5: Commit**

```bash
git add app/web/src app/web/dist
git commit -m "feat: ndvi timeline, demand panel and method page"
```

---

## Task 19: systemd-Unit

**Files:**
- Create: `systemd/fieldwatch.service`
- Test: `tests/static-checks.sh` (Teil 1)

**Interfaces:**
- Consumes: `@APP_DIR@`, `@APP_PORT@` Platzhalter
- Produces: installierbare Unit

- [ ] **Step 1: `systemd/fieldwatch.service` schreiben**

```ini
[Unit]
Description=FieldWatch - lokale Feld- und Bewaesserungsanalyse (Web-UI :@APP_PORT@)
Documentation=https://github.com/HatchetMan111/FeldWatch
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=fieldwatch
Group=fieldwatch
WorkingDirectory=@APP_DIR@
EnvironmentFile=/etc/fieldwatch/config.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=HOME=/var/lib/fieldwatch
ExecStart=@APP_DIR@/venv/bin/uvicorn fieldwatch.api:app_factory --factory --host 0.0.0.0 --port @APP_PORT@ --app-dir @APP_DIR@/src
Restart=always
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/fieldwatch

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Unit-Syntax prüfen**

Run: `systemd-analyze verify systemd/fieldwatch.service 2>&1 | head -20 || true`
Expected: keine Fehler außer ggf. „Executable not found" (Platzhalter noch nicht ersetzt) — das ist erwartet. Wenn `systemd-analyze` fehlt, Schritt überspringen.

- [ ] **Step 3: Commit**

```bash
git add systemd/fieldwatch.service
git commit -m "feat: systemd unit for fieldwatch"
```

---

## Task 20: Container-Inneninstaller

**Files:**
- Create: `install/fieldwatch-inner.sh`

**Interfaces:**
- Consumes: Argumente `--port`, `--state`, `--basemap`, `--repo`, `--ref`, `--debug`
- Produces: laufender Dienst, `/etc/fieldwatch/config.env`, `/var/log/fieldwatch-install.log`

- [ ] **Step 1: `install/fieldwatch-inner.sh` schreiben**

```bash
#!/usr/bin/env bash
#
# fieldwatch-inner.sh - laeuft INNERHALB des LXC.
# Installiert FieldWatch, schreibt die systemd-Unit und startet den Dienst.
#
set -euo pipefail

APP_ID="fieldwatch"
APP_DIR="/opt/fieldwatch"
DATA_DIR="/var/lib/fieldwatch"
CONF_DIR="/etc/fieldwatch"
PORT="8080"
STATE_CODE="none"
BASEMAP="local"
REPO_URL="https://github.com/HatchetMan111/FeldWatch"
REPO_REF="main"
DEBUG=0
LOG_FILE="/var/log/fieldwatch-install.log"

msg_info()  { echo -e "\e[34m[INFO]\e[0m  $*"; }
msg_ok()    { echo -e "\e[32m[OK]\e[0m    $*"; }
msg_warn()  { echo -e "\e[33m[WARN]\e[0m  $*"; }
msg_error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; }
die()       { msg_error "$*"; exit 1; }

on_error() {
  local code=$1 line=$2 cmd=$3
  trap - ERR
  {
    echo
    msg_error "Abbruch (Exit ${code}) in Zeile ${line}: ${cmd}"
    echo "--- Install-Log (letzte 60 Zeilen) ---"
    tail -n 60 "$LOG_FILE" 2>/dev/null || true
    echo "--- systemctl status ---"
    systemctl status "$APP_ID" --no-pager -l 2>&1 | tail -n 40 || true
    echo "--- journalctl ---"
    journalctl -u "$APP_ID" -n 60 --no-pager 2>&1 || true
    echo "--- Ports ---"
    ss -tlnp 2>&1 | head -20 || true
    echo
    echo "Naechster Schritt: erneut mit --debug ausfuehren:"
    echo "  bash /root/fieldwatch-inner.sh --debug --port ${PORT}"
  } >&2
  exit "$code"
}
trap 'on_error $? $LINENO "$BASH_COMMAND"' ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --state) STATE_CODE="$2"; shift 2;;
    --basemap) BASEMAP="$2"; shift 2;;
    --repo) REPO_URL="$2"; shift 2;;
    --ref) REPO_REF="$2"; shift 2;;
    --debug) DEBUG=1; shift;;
    *) die "Unbekannte Option: $1";;
  esac
done

if [[ "$DEBUG" == "1" ]]; then
  export PS4='+ $(date +%H:%M:%S) ${BASH_SOURCE##*/}:${LINENO}: '
  exec > >(tee -a "$LOG_FILE") 2>&1
  set -x
else
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

msg_info "FieldWatch Installation startet (Port ${PORT}, Land ${STATE_CODE})"

msg_info "Pakete aktualisieren"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git python3 python3-venv python3-dev \
  build-essential gdal-bin libgdal-dev sqlite3 ufw jq >/dev/null
msg_ok "Pakete installiert"

if ! id "$APP_ID" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_ID"
  msg_ok "Benutzer ${APP_ID} angelegt"
fi

mkdir -p "$APP_DIR" "$DATA_DIR" "$CONF_DIR"
chown -R "$APP_ID:$APP_ID" "$DATA_DIR"

msg_info "Code laden von ${REPO_URL} (${REPO_REF})"
TMP_DIR="$(mktemp -d)"
git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$TMP_DIR/src" \
  || die "git clone fehlgeschlagen: ${REPO_URL} (${REPO_REF})"
rm -rf "${APP_DIR:?}/"*
cp -a "$TMP_DIR/src/app/." "$APP_DIR/"
mkdir -p "$APP_DIR/data"
cp -a "$TMP_DIR/src/data/." "$APP_DIR/data/"
cp -a "$TMP_DIR/src/systemd" "$APP_DIR/systemd" 2>/dev/null || true
rm -rf "$TMP_DIR"
chown -R "$APP_ID:$APP_ID" "$APP_DIR"
msg_ok "Code in ${APP_DIR}"

msg_info "Python-Umgebung"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip wheel
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$APP_DIR/venv/bin/pip" install --quiet -e "$APP_DIR"
"$APP_DIR/venv/bin/python" -c "import fieldwatch, fastapi, rasterio, fiona"
msg_ok "Python-Abhaengigkeiten installiert"

msg_info "Konfiguration schreiben"
cat > "$CONF_DIR/config.env" <<EOF
FIELDWATCH_STATE=${STATE_CODE}
FIELDWATCH_PORT=${PORT}
FIELDWATCH_BASEMAP=${BASEMAP}
FIELDWATCH_DATA_DIR=${DATA_DIR}
FIELDWATCH_REPO_REF=${REPO_REF}
FIELDWATCH_SCHEDULER=1
EOF
chmod 600 "$CONF_DIR/config.env"
chown root:root "$CONF_DIR/config.env"
msg_ok "Konfiguration in ${CONF_DIR}/config.env"

msg_info "systemd-Unit installieren"
sed -e "s|@APP_DIR@|${APP_DIR}|g" -e "s|@APP_PORT@|${PORT}|g" \
  "$APP_DIR/systemd/fieldwatch.service" > "/etc/systemd/system/${APP_ID}.service"
systemctl daemon-reload
systemctl enable "$APP_ID" >/dev/null 2>&1
systemctl restart "$APP_ID"
msg_ok "Dienst ${APP_ID}.service aktiviert"

msg_info "Firewall (nur LAN)"
if ufw --force reset >/dev/null 2>&1 \
  && ufw default deny incoming >/dev/null 2>&1 \
  && ufw default allow outgoing >/dev/null 2>&1; then
  for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
    ufw allow from "$net" to any port "$PORT" proto tcp >/dev/null 2>&1 || true
  done
  if ufw --force enable >/dev/null 2>&1; then
    msg_ok "ufw: Port ${PORT} nur aus RFC1918"
  else
    msg_warn "ufw konnte nicht aktiviert werden (LXC ohne CAP_NET_ADMIN) - Schutz erfolgt ueber die LAN-Grenze"
  fi
else
  msg_warn "ufw nicht verfuegbar (LXC) - Schutz erfolgt ueber die LAN-Grenze"
fi

msg_info "Healthcheck"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
if [[ "$ok" != "1" ]]; then
  die "Web-UI antwortet nicht auf http://127.0.0.1:${PORT}/healthz"
fi
systemctl is-active --quiet "$APP_ID" || die "Dienst ${APP_ID} laeuft nicht"
msg_ok "Dienst laeuft, /healthz antwortet"

echo
msg_ok "FieldWatch ist bereit."
```

- [ ] **Step 2: Syntax prüfen**

Run: `bash -n install/fieldwatch-inner.sh && echo OK`
Expected: `OK`

- [ ] **Step 3: Shellcheck falls vorhanden**

Run: `command -v shellcheck >/dev/null && shellcheck -S warning install/fieldwatch-inner.sh || echo "shellcheck nicht installiert"`
Expected: keine Fehler (oder Hinweis, dass shellcheck fehlt)

- [ ] **Step 4: Commit**

```bash
chmod +x install/fieldwatch-inner.sh
git add install/fieldwatch-inner.sh
git commit -m "feat: in-container installer"
```

---

## Task 21: Statische Prüfungen

**Files:**
- Modify: `tests/static-checks.sh`

**Interfaces:**
- Consumes: Repo-Dateien
- Produces: Exit 0 bei Erfolg

- [ ] **Step 1: `tests/static-checks.sh` ersetzen**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
ok()   { echo "ok   $*"; }
bad()  { echo "FAIL $*"; fail=1; }

check_file() {
  [[ -f "$1" ]] && ok "$1" || bad "$1 fehlt"
}

for f in install/fieldwatch.sh install/fieldwatch-inner.sh systemd/fieldwatch.service \
         README.md NOTICE app/requirements.txt app/pyproject.toml data/states.json \
         app/web/dist/index.html; do
  check_file "$f"
done

for f in install/fieldwatch.sh install/fieldwatch-inner.sh; do
  [[ -f "$f" ]] || continue
  bash -n "$f" && ok "bash -n $f" || bad "bash -n $f"
  grep -q '^set -euo pipefail' "$f" && ok "strict mode $f" || bad "set -euo pipefail fehlt in $f"
  grep -q 'trap .*ERR' "$f" && ok "ERR-Trap $f" || bad "ERR-Trap fehlt in $f"
done

grep -q '^User=fieldwatch' systemd/fieldwatch.service && ok "unit User" || bad "unit User"
grep -q '@APP_DIR@' systemd/fieldwatch.service && ok "unit Platzhalter APP_DIR" || bad "unit Platzhalter APP_DIR"
grep -q 'Restart=always' systemd/fieldwatch.service && ok "unit Restart" || bad "unit Restart"

grep -q 'raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh' README.md \
  && ok "README Einzeiler" || bad "README Einzeiler passt nicht"

if command -v python3 >/dev/null; then
  python3 -m compileall -q app/src >/dev/null && ok "python compileall" || bad "python compileall"
fi

if [[ -f data/states.json ]]; then
  count=$(python3 -c "import json;print(len(json.load(open('data/states.json'))['states']))")
  [[ "$count" == "16" ]] && ok "16 Bundeslaender" || bad "Bundeslaender: $count statt 16"
fi

if command -v shellcheck >/dev/null; then
  shellcheck -S warning install/*.sh tests/*.sh && ok "shellcheck" || bad "shellcheck"
fi

if [[ "$fail" == "1" ]]; then
  echo "static-checks: FEHLGESCHLAGEN"
  exit 1
fi
echo "static-checks: OK"
```

- [ ] **Step 2: Ausführen**

Run: `bash tests/static-checks.sh`
Expected: FAIL für `install/fieldwatch.sh` (noch nicht vorhanden) — das ist der erwartete Zwischenstand; nach Task 22 ist alles grün.

- [ ] **Step 3: Commit**

```bash
chmod +x tests/static-checks.sh
git add tests/static-checks.sh
git commit -m "test: static checks for scripts, unit and readme"
```

---

## Task 22: Host-Installer

**Files:**
- Create: `install/fieldwatch.sh`

**Interfaces:**
- Consumes: Proxmox CLI
- Produces: LXC + installierte App; Exit 0 nur bei erfolgreichem Healthcheck

- [ ] **Step 1: `install/fieldwatch.sh` schreiben**

```bash
#!/usr/bin/env bash
#
# fieldwatch.sh - Proxmox VE Installer fuer FieldWatch
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)"
#
set -euo pipefail

APP="FieldWatch"
APP_ID="fieldwatch"
APP_PORT=8080
CTID=""
CT_HOSTNAME="fieldwatch"
CORES=2
RAM_MB=2048
SWAP_MB=2048
DISK_GB=16
STORAGE=""
TEMPLATE_STORAGE="local"
BRIDGE="vmbr0"
STATE_CODE="ask"
BASEMAP="local"
REPO_URL="https://github.com/HatchetMan111/FeldWatch"
REPO_REF="main"
FORCE=0
ASSUME_YES=0
DEBUG=0
PASSWORD=""
LOG_FILE="/var/log/fieldwatch-install.log"
INNER_TMP=""

msg_info()  { echo -e "\e[34m[INFO]\e[0m  $*"; }
msg_ok()    { echo -e "\e[32m[OK]\e[0m    $*"; }
msg_warn()  { echo -e "\e[33m[WARN]\e[0m  $*"; }
msg_error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; }
die()       { msg_error "$*"; exit 1; }

on_error() {
  local code=$1 line=$2 cmd=$3
  trap - ERR
  {
    echo
    msg_error "Abbruch (Exit ${code}) in Zeile ${line}: ${cmd}"
    if [[ -n "${CTID:-}" ]] && pct status "$CTID" >/dev/null 2>&1; then
      echo "--- Container-Status ---"
      pct status "$CTID" 2>&1 || true
      echo "--- Container-Install-Log (letzte 60 Zeilen) ---"
      pct exec "$CTID" -- tail -n 60 /var/log/fieldwatch-install.log 2>&1 || true
      echo "--- journalctl -u ${APP_ID} ---"
      pct exec "$CTID" -- journalctl -u "$APP_ID" -n 60 --no-pager 2>&1 || true
      echo "--- Ports im Container ---"
      pct exec "$CTID" -- ss -tlnp 2>&1 | head -20 || true
    fi
    echo "--- Host-Log: ${LOG_FILE} ---"
    tail -n 60 "$LOG_FILE" 2>/dev/null || true
    echo
    echo "Naechster Schritt:"
    echo "  pct enter ${CTID:-<ID>}"
    echo "  bash /root/fieldwatch-inner.sh --debug --port ${APP_PORT}"
    echo "oder Installer erneut mit --debug starten."
  } >&2
  exit "$code"
}
trap 'on_error $? $LINENO "$BASH_COMMAND"' ERR

usage() {
  cat <<EOF
${APP} - Proxmox VE Installer

Usage: bash fieldwatch.sh [OPTIONEN]

  --ctid ID            CT-ID (Default: naechste freie)
  --hostname NAME      Container-Hostname (Default: ${CT_HOSTNAME})
  --cores N            vCPUs (Default: ${CORES})
  --ram MB             RAM in MiB (Default: ${RAM_MB})
  --disk GB            Disk in GiB (Default: ${DISK_GB})
  --storage NAME       Storage fuer die Disk (Default: automatisch)
  --template-storage N Storage fuer das Template (Default: ${TEMPLATE_STORAGE})
  --bridge NAME        Linux-Bridge (Default: ${BRIDGE})
  --port N             Web-Port (Default: ${APP_PORT})
  --bundesland CODE    BW,BY,BE,BB,HB,HH,HE,MV,NI,NW,RP,SL,SN,ST,SH,TH oder none
  --basemap local|osm  Kartenhintergrund (Default: ${BASEMAP})
  --repo URL           Git-Repo (Default: ${REPO_URL})
  --ref REF            Branch/Tag (Default: ${REPO_REF})
  --password PW        root-Passwort im Container (Default: zufaellig)
  --force              bestehende Installation ueberschreiben
  --yes                nicht-interaktiv, Defaults verwenden
  --debug              bash -x + erweiterte Diagnose
  -h, --help           Hilfe
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ctid) CTID="$2"; shift 2;;
    --hostname) CT_HOSTNAME="$2"; shift 2;;
    --cores) CORES="$2"; shift 2;;
    --ram) RAM_MB="$2"; shift 2;;
    --disk) DISK_GB="$2"; shift 2;;
    --storage) STORAGE="$2"; shift 2;;
    --template-storage) TEMPLATE_STORAGE="$2"; shift 2;;
    --bridge) BRIDGE="$2"; shift 2;;
    --port) APP_PORT="$2"; shift 2;;
    --bundesland) STATE_CODE="$2"; shift 2;;
    --basemap) BASEMAP="$2"; shift 2;;
    --repo) REPO_URL="$2"; shift 2;;
    --ref) REPO_REF="$2"; shift 2;;
    --password) PASSWORD="$2"; shift 2;;
    --force) FORCE=1; shift;;
    --yes) ASSUME_YES=1; shift;;
    --debug) DEBUG=1; shift;;
    -h|--help) usage; exit 0;;
    *) die "Unbekannte Option: $1";;
  esac
done

if [[ "$DEBUG" == "1" ]]; then
  export PS4='+ $(date +%H:%M:%S) ${BASH_SOURCE##*/}:${LINENO}: '
  exec > >(tee -a "$LOG_FILE") 2>&1
  set -x
else
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

msg_info "${APP} Installer"

[[ "$(id -u)" == "0" ]] || die "Bitte als root auf dem Proxmox-Host ausfuehren."
command -v pct >/dev/null || die "pct nicht gefunden - kein Proxmox-VE-Host?"
command -v pveam >/dev/null || die "pveam nicht gefunden"
command -v pvesh >/dev/null || die "pvesh nicht gefunden"
[[ -d /etc/pve ]] || die "/etc/pve fehlt - kein Proxmox-VE-Host?"

msg_info "Internet pruefen"
curl -fsS --max-time 10 -o /dev/null "https://earth-search.aws.element84.com/v1" \
  || msg_warn "Earth Search nicht erreichbar - Analyse wird spaeter scheitern"
curl -fsS --max-time 10 -o /dev/null "https://api.open-meteo.com/v1/forecast?latitude=51&longitude=7&daily=et0_fao_evapotranspiration&forecast_days=1" \
  || msg_warn "Open-Meteo nicht erreichbar"
msg_ok "Netzwerkpruefung abgeschlossen"

if [[ -z "$CTID" ]]; then
  CTID="$(pvesh get /cluster/nextid 2>/dev/null | tr -d '"' | tr -d '[:space:]')"
  [[ "$CTID" =~ ^[0-9]+$ ]] || die "Konnte keine freie CT-ID ermitteln"
fi
msg_ok "CT-ID: ${CTID}"

EXISTING_HOST=""
if pct config "$CTID" >/dev/null 2>&1; then
  EXISTING_HOST="$(pct config "$CTID" | awk -F': ' '/^hostname:/{print $2}')"
  if [[ "$EXISTING_HOST" == "$CT_HOSTNAME" ]]; then
    msg_warn "CT ${CTID} (${CT_HOSTNAME}) existiert - Update-Modus"
    UPDATE_ONLY=1
    if [[ "$(pct status "$CTID" | awk '{print $2}')" != "running" ]]; then
      msg_info "Container starten"
      pct start "$CTID"
      for _ in $(seq 1 30); do
        [[ "$(pct status "$CTID" | awk '{print $2}')" == "running" ]] && break
        sleep 1
      done
    fi
  else
    if [[ "$FORCE" == "1" ]]; then
      msg_warn "CT ${CTID} (${EXISTING_HOST}) wird auf Wunsch (--force) entfernt und neu erstellt"
      pct stop "$CTID" 2>/dev/null || true
      pct destroy "$CTID" --purge
      UPDATE_ONLY=0
    else
      die "CT ${CTID} existiert bereits mit Hostname '${EXISTING_HOST}'. Andere ID waehlen oder --force."
    fi
  fi
else
  UPDATE_ONLY=0
fi

ask_state() {
  local options=(
    "none" "Kein Bundesland / nur eigene Polygone"
    "BW"   "Baden-Wuerttemberg"
    "BY"   "Bayern"
    "BE"   "Berlin"
    "BB"   "Brandenburg"
    "HB"   "Bremen"
    "HH"   "Hamburg"
    "HE"   "Hessen"
    "MV"   "Mecklenburg-Vorpommern"
    "NI"   "Niedersachsen"
    "NW"   "Nordrhein-Westfalen"
    "RP"   "Rheinland-Pfalz"
    "SL"   "Saarland"
    "SN"   "Sachsen"
    "ST"   "Sachsen-Anhalt"
    "SH"   "Schleswig-Holstein"
    "TH"   "Thueringen"
  )
  whiptail --title "Bundesland" --menu "Region fuer Feldblock-Aufloesung:" 26 78 18 "${options[@]}" 3>&1 1>&2 2>&3
}

if [[ "$ASSUME_YES" != "1" && -t 0 ]]; then
  if [[ "$STATE_CODE" == "ask" ]]; then
    STATE_CODE="$(ask_state)" || die "Bundesland-Auswahl abgebrochen"
  fi
  if ! whiptail --title "Ressourcen" --yesno "CT ${CTID}: ${CORES} vCPU, ${RAM_MB} MB RAM, ${DISK_GB} GB Disk, Port ${APP_PORT}.\n\nFortfahren?" 12 70; then
    die "Vom Benutzer abgebrochen"
  fi
else
  if [[ "$STATE_CODE" == "ask" ]]; then STATE_CODE="none"; fi
fi
msg_ok "Bundesland: ${STATE_CODE}"

if [[ "$UPDATE_ONLY" == "0" ]]; then
  msg_info "Template suchen"
  pveam update >/dev/null 2>&1 || true
  TEMPLATE="$(pveam available --section system | awk '/debian-12-standard/{print $2; exit}')"
  [[ -n "$TEMPLATE" ]] || die "Kein debian-12-standard Template verfuegbar"
  if ! pveam list "$TEMPLATE_STORAGE" | grep -q "$TEMPLATE"; then
    msg_info "Template herunterladen: ${TEMPLATE}"
    pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
  fi
  TEMPLATE_PATH="$(pveam list "$TEMPLATE_STORAGE" | awk -v t="$TEMPLATE" 'index($0,t){print $1; exit}')"
  [[ -f "$TEMPLATE_PATH" ]] || die "Template-Pfad nicht gefunden"

  if [[ -z "$STORAGE" ]]; then
    STORAGE="$(pvesm status --content rootdir | awk 'NR==2{print $1}')"
  fi
  [[ -n "$STORAGE" ]] || die "Kein Storage mit content rootdir gefunden"
  msg_ok "Storage: ${STORAGE}"

  [[ -n "$PASSWORD" ]] || PASSWORD="$(openssl rand -base64 18 | tr -d '/+=')"

  msg_info "Container ${CTID} erstellen"
  pct create "$CTID" "$TEMPLATE_PATH" \
    --hostname "$CT_HOSTNAME" \
    --cores "$CORES" \
    --memory "$RAM_MB" \
    --swap "$SWAP_MB" \
    --rootfs "${STORAGE}:${DISK_GB}" \
    --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
    --unprivileged 1 \
    --onboot 1 \
    --ostype debian \
    --password "$PASSWORD" \
    --description "FieldWatch - lokale Feld- und Bewaesserungsanalyse"
  pct start "$CTID"
  msg_ok "Container erstellt und gestartet"
else
  pct status "$CTID" | grep -q running || pct start "$CTID"
fi

msg_info "Auf Netzwerk im Container warten"
ready=0
for _ in $(seq 1 120); do
  if pct exec "$CTID" -- getent hosts deb.debian.org >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == "1" ]] || die "Container hat nach 120s kein DNS/Netz"

msg_info "Inner-Installer uebertragen"
LOCAL_INNER="$(dirname -- "${BASH_SOURCE[0]:-}")/fieldwatch-inner.sh"
if [[ -f "$LOCAL_INNER" ]]; then
  INNER_TMP="$LOCAL_INNER"
else
  INNER_TMP="$(mktemp)"
  RAW_BASE="${REPO_URL/github.com/raw.githubusercontent.com}"
  curl -fsSL "${RAW_BASE}/${REPO_REF}/install/fieldwatch-inner.sh" -o "$INNER_TMP" \
    || die "Inner-Installer konnte nicht geladen werden"
fi
pct push "$CTID" "$INNER_TMP" /root/fieldwatch-inner.sh --perms 700
if [[ "$INNER_TMP" != "$LOCAL_INNER" ]]; then rm -f "$INNER_TMP"; fi

msg_info "Installation im Container (kann einige Minuten dauern)"
EXTRA=()
if [[ "$DEBUG" == "1" ]]; then EXTRA+=(--debug); fi
pct exec "$CTID" -- bash /root/fieldwatch-inner.sh \
  --port "$APP_PORT" --state "$STATE_CODE" --basemap "$BASEMAP" \
  --repo "$REPO_URL" --ref "$REPO_REF" ${EXTRA[@]+"${EXTRA[@]}"}

msg_info "Verifikation vom Host"
ok=0
for _ in $(seq 1 45); do
  if pct exec "$CTID" -- curl -fsS "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
[[ "$ok" == "1" ]] || die "Healthcheck im Container fehlgeschlagen"
pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" || die "Dienst nicht aktiv"
msg_ok "Dienst aktiv, /healthz antwortet"

CT_IP="$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')"
[[ -n "$CT_IP" ]] || CT_IP="<IP ermitteln mit: pct exec ${CTID} -- hostname -I>"

cat <<EOF

  ${APP} ist installiert.

  Web-UI:      http://${CT_IP}:${APP_PORT}
  CT-ID:       ${CTID}
  Hostname:    ${CT_HOSTNAME}
  Bundesland:  ${STATE_CODE}
  root-PW:     ${PASSWORD:-unveraendert (Update)}

  Update:      bash -c "\$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)" -- --ctid ${CTID}
  Shell:       pct enter ${CTID}
  Logs:        pct exec ${CTID} -- journalctl -u ${APP_ID} -f
  Entfernen:   pct stop ${CTID} && pct destroy ${CTID} --purge

EOF
```

- [ ] **Step 2: Syntax prüfen**

Run: `bash -n install/fieldwatch.sh && echo OK`
Expected: `OK`

- [ ] **Step 3: Statische Prüfungen**

Run: `bash tests/static-checks.sh`
Expected: `static-checks: OK`

- [ ] **Step 4: Commit**

```bash
chmod +x install/fieldwatch.sh
git add install/fieldwatch.sh
git commit -m "feat: proxmox host installer with whiptail and verification"
```

---

## Task 23: Reboot-Test

**Files:**
- Create: `tests/reboot-test.sh`

**Interfaces:**
- Consumes: CT-ID, optional IP, Port
- Produces: Exit 0 nach erfolgreichem Reboot-Zyklus

- [ ] **Step 1: `tests/reboot-test.sh` schreiben**

```bash
#!/usr/bin/env bash
set -euo pipefail

CTID="${1:?Usage: reboot-test.sh <CTID> [IP] [PORT]}"
IP="${2:-}"
PORT="${3:-8080}"
APP_ID="fieldwatch"

pass() { echo "ok   $*"; }
bad()  { echo "FAIL $*"; exit 1; }

[[ "$(id -u)" == "0" ]] || bad "als root auf dem Proxmox-Host ausfuehren"

echo "== vor dem Reboot =="
pct status "$CTID" | grep -q running || pct start "$CTID"
pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" || bad "Dienst nicht aktiv"
pass "Dienst aktiv"
pct exec "$CTID" -- curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null || bad "healthz antwortet nicht"
pass "healthz antwortet"

echo "== Reboot =="
pct reboot "$CTID"
for _ in $(seq 1 90); do
  if pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" 2>/dev/null; then break; fi
  sleep 2
done

echo "== nach dem Reboot =="
pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" || bad "Dienst nach Reboot nicht aktiv"
pass "Dienst automatisch gestartet"
pct exec "$CTID" -- curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null || bad "healthz nach Reboot"
pass "healthz antwortet"
[[ "$(pct config "$CTID" | awk -F': ' '/^onboot:/{print $2}')" == "1" ]] || bad "onboot ist nicht 1"
pass "onboot=1"

if [[ -n "$IP" ]]; then
  curl -fsS "http://${IP}:${PORT}/healthz" >/dev/null || bad "Web-UI von aussen nicht erreichbar"
  pass "Web-UI erreichbar unter http://${IP}:${PORT}"
fi

echo "reboot-test: OK"
```

- [ ] **Step 2: Syntax prüfen**

Run: `bash -n tests/reboot-test.sh && bash tests/static-checks.sh`
Expected: `static-checks: OK`

- [ ] **Step 3: Commit**

```bash
chmod +x tests/reboot-test.sh
git add tests/reboot-test.sh
git commit -m "test: reboot verification script"
```

---

## Task 24: README und Attribution

**Files:**
- Create: `README.md`, `NOTICE`

**Interfaces:**
- Consumes: Einzeiler-Pfad
- Produces: dokumentierter Einstieg für Nutzer

- [ ] **Step 1: `NOTICE` schreiben**

```text
FieldWatch - Attribution und Lizenzen
=====================================

Daten und Dienste
-----------------
Sentinel-2 L2A
  Enthaelt modifizierte Copernicus-Sentinel-Daten.
  Zugriff ueber AWS Earth Search (Element 84).
  https://registry.opendata.aws/sentinel-2-l2a-cogs/

Open-Meteo
  Weather data by Open-Meteo.com
  Lizenz: CC BY 4.0
  https://open-meteo.com/

Boden- und Modellgrundlage
--------------------------
Trout, T.J. & Johnson, L.F. (2007): Estimating crop water use from
remotely sensed NDVI, crop coefficients, and reference evapotranspiration.
USDA-ARS. Formeln:
  CC  = 1.22 * NDVI - 0.21   (0 <= CC <= 0.8)
  Kcb = 1.13 * CC + 0.14

Abgrenzung
----------
Dieses Projekt ist eine eigenstaendige Umsetzung der oeffentlich
dokumentierten Methode. Es uebernimmt keine Inhalte, kein Design, keinen
Namen und keinen Code von epicfields.app.
```

- [ ] **Step 2: `README.md` schreiben**

```markdown
# FieldWatch auf Proxmox VE

Ein Einzeiler-Installer im Stil der Proxmox Community Scripts: Erstellt einen
Debian-12-LXC, installiert FieldWatch und richtet einen reboot-festen
`systemd`-Dienst ein. Die Web-UI ist nur im LAN erreichbar.

FieldWatch zeigt pro Feld eine Wachstumsanimation aus echten
Sentinel-2-Aufnahmen der letzten 12 Monate und den Wasserbedarf der naechsten
7 Tage (NDVI -> Cover -> Kcb x FAO-56 ETo).

## Was wird installiert?

| Komponente | Detail |
|---|---|
| Container | Debian 12, LXC, unprivileged, `onboot=1` |
| Ressourcen | 2 vCPU, 2048 MB RAM, 2048 MB Swap, 16 GB Disk |
| Dienst | `fieldwatch.service`, `Restart=always`, `After=network-online.target` |
| Stack | Python 3.11, FastAPI, rasterio, SQLite, React-Build (statisch) |
| Daten | `/var/lib/fieldwatch` (SQLite, COG-Cache, Feldbloecke) |
| Web-UI | `http://<CT-IP>:8080` |

## Voraussetzungen

- Proxmox VE 8.x, root-SSH auf dem Host
- Internetzugang des Containers (Sentinel-2, Open-Meteo)
- 20 GB freier Storage

## Schnellstart

Auf dem **Proxmox-Host** als root:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)"
```

Das Script fragt Bundesland und Ressourcen ab, waehlt die naechste freie
CT-ID, erstellt den Container und installiert die App. Dauer: 5-10 Minuten.

Am Ende wird die URL ausgegeben:

```text
Web-UI: http://192.168.1.50:8080
```

## Optionen

```text
--ctid ID            CT-ID (Default: naechste freie)
--hostname NAME      Default: fieldwatch
--cores N            Default: 2
--ram MB             Default: 2048
--disk GB            Default: 16
--storage NAME       Default: automatisch
--bridge NAME        Default: vmbr0
--port N             Default: 8080
--bundesland CODE    BW,BY,BE,BB,HB,HH,HE,MV,NI,NW,RP,SL,SN,ST,SH,TH,none
--basemap local|osm  Default: local
--repo URL           Default: https://github.com/HatchetMan111/FeldWatch
--ref REF            Default: main
--password PW        root-Passwort im Container
--force              bestehende Installation ueberschreiben
--yes                nicht-interaktiv
--debug              bash -x + erweiterte Diagnose
```

Beispiel:

```bash
bash install/fieldwatch.sh --bundesland NW --ram 4096 --disk 32 --port 8080 --yes
```

## Nach der Installation

1. `http://<CT-IP>:8080` oeffnen.
2. Auf die Karte tippen (Feldblock, falls importiert) oder ein Polygon zeichnen.
3. Feld speichern, Analyse starten, Zeitachse abspielen.

### Feldbloecke

Fuer Laender mit `status: pending` in `data/states.json` gibt es noch keinen
Import. Bis dahin gilt der Zeichnen-Modus. Ein Feldblock-Datensatz kann
manuell importiert werden:

```bash
pct exec <CTID> -- /opt/fieldwatch/venv/bin/python -c \
  "from pathlib import Path; from fieldwatch.parcels import import_file; \
   print(import_file(Path('/root/felder.gpkg'), 'NW', Path('/var/lib/fieldwatch/parcels')))"
```

Danach den Dienst neu starten: `pct exec <CTID> -- systemctl restart fieldwatch`.

### Update

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)" -- --ctid <CTID>
```

Daten in `/var/lib/fieldwatch` bleiben erhalten.

### Deinstallation

```bash
pct stop <CTID> && pct destroy <CTID> --purge
```

## Test und Diagnose

```bash
# ohne Proxmox
bash tests/static-checks.sh

# auf dem Proxmox-Host nach der Installation
bash tests/reboot-test.sh <CTID> <CT-IP> 8080

# Logs
pct exec <CTID> -- journalctl -u fieldwatch -f
pct exec <CTID> -- tail -n 200 /var/log/fieldwatch-install.log
```

Bei Fehlern zeigt der Installer Exit-Code, Zeile, Befehl, Host-Log,
Container-Log, `pct status` und `journalctl`. Fuer ein vollstaendiges Trace:

```bash
bash install/fieldwatch.sh --debug --ctid <CTID>
```

## Grenzen

- **Nur LAN.** Kein TLS, keine Domain, kein Login. Nicht ins Internet stellen.
- **Datenquelle Internet.** Die App laeuft lokal, Sentinel-2 und Open-Meteo
  werden aber online abgefragt.
- **Modell.** Kalibriert fuer gruene Blaetter und CC <= 0,8. Ergebnis ist
  Bedarf, keine Bewaesserungsanweisung.
- **Feldbloecke.** Nur Laender mit Status `available` loesen per Tap auf.
- **Kein Markenklon.** Name, Design und Texte sind eigenstaendig.

## Projektstruktur

```text
FeldWatch/
├── install/
│   ├── fieldwatch.sh          # Host: LXC, Whiptail, Verifikation
│   └── fieldwatch-inner.sh    # Container: Pakete, App, systemd, ufw
├── systemd/fieldwatch.service
├── app/
│   ├── src/fieldwatch/        # Pipeline + API
│   ├── tests/                 # pytest
│   └── web/                   # React + MapLibre, dist eingecheckt
├── data/states.json
├── tests/
│   ├── static-checks.sh
│   └── reboot-test.sh
├── NOTICE
└── README.md
```

## Credits

- Copernicus Sentinel-2 (ESA), AWS Earth Search (Element 84)
- Open-Meteo (CC BY 4.0)
- Trout & Johnson (2007), USDA-ARS
- Installer-Struktur inspiriert von den Proxmox Community Scripts
```

- [ ] **Step 3: Statische Prüfungen**

Run: `bash tests/static-checks.sh`
Expected: `static-checks: OK`

- [ ] **Step 4: Commit**

```bash
git add README.md NOTICE
git commit -m "docs: readme, options, limits and attribution"
```

---

## Task 25: Abnahme

**Files:**
- Modify: `README.md` (Testprotokoll-Abschnitt)

**Interfaces:**
- Consumes: alles
- Produces: belegter Installations- und Reboot-Durchlauf

- [ ] **Step 1: Vollständige lokale Prüfung**

```bash
cd app && .venv/bin/python -m pytest -q
cd ../web && npm test && npm run build
cd ../..
bash tests/static-checks.sh
```

Expected: alle grün, `static-checks: OK`.

- [ ] **Step 2: Pipeline-Smoke gegen echte APIs**

```bash
cd app
.venv/bin/python -m fieldwatch.cli run --lat 51.2 --lon 7.0 --radius 150 --out /tmp/fw-smoke.json
python3 -c "import json;d=json.load(open('/tmp/fw-smoke.json'));print(len(d['observations']),'scenes');print(d['demand']['status'],d['demand'].get('week_mm'))"
```

Expected: mindestens 5 Beobachtungen, `demand.status` in `{ok, partial}`, `week_mm` > 0. Bei `no_clear_observation` Standort/Zeitraum variieren und Ergebnis im README notieren.

- [ ] **Step 3: Installation auf echtem Proxmox-Host**

```bash
bash install/fieldwatch.sh --yes --bundesland none
```

Expected: Exit 0, Banner mit `http://<IP>:8080`.

- [ ] **Step 4: Reboot-Test**

```bash
bash tests/reboot-test.sh <CTID> <IP> 8080
```

Expected: `reboot-test: OK`.

- [ ] **Step 5: Ergebnis dokumentieren**

In `README.md` unter „Test und Diagnose" ergänzen:

```markdown
### Testprotokoll

- `pytest`: __ Tests, alle grün
- `npm test`: __ Tests, alle grün
- `static-checks.sh`: OK
- CLI-Smoke (51.2/7.0, 12 Monate): __ Beobachtungen, Demand __ mm
- Installation LXC __: OK, Healthcheck OK
- Reboot-Test: OK, Web-UI nach Reboot erreichbar
```

- [ ] **Step 6: Commit und Push**

```bash
git add README.md
git commit -m "docs: record acceptance results"
git push -u origin main
```

---

## Execution Notes

- Reihenfolge ist verbindlich: Tasks 1–10 liefern die reine Rechenkette (kein Netz), 11–16 die HTTP-Schicht, 17–18 die UI, 19–24 den Betrieb.
- Netzwerkzugriffe nur in Task 6, 7, 8, 22 und im Smoke-Test (Task 25). Alle Tests davor laufen offline.
- `app/web/dist/` wird bewusst eingecheckt, damit der Container kein Node braucht.
- Nach jedem Task `pytest -q` laufen lassen; ein roter Test blockiert den nächsten Task.

