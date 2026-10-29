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
