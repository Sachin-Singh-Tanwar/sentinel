"""SQLite storage (WAL) — SPEC §12."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "var" / "sentinel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    http_status     INTEGER,
    records         INTEGER NOT NULL DEFAULT 0,
    schema_failures INTEGER NOT NULL DEFAULT 0,
    required_nulls  INTEGER NOT NULL DEFAULT 0,
    layout_rev      INTEGER NOT NULL DEFAULT 1,
    staged          INTEGER NOT NULL DEFAULT 0,
    extractor       TEXT,
    snapshot        TEXT,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS runs_source_id ON runs(source, id);

CREATE TABLE IF NOT EXISTS records (
    run_id  INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    idx     INTEGER NOT NULL,
    payload TEXT    NOT NULL,
    valid   INTEGER NOT NULL,
    PRIMARY KEY (run_id, idx)
);

CREATE TABLE IF NOT EXISTS source_state (
    source             TEXT PRIMARY KEY,
    state              TEXT NOT NULL,
    drift_score        REAL,
    updated_at         TEXT NOT NULL,
    last_run_id        INTEGER,
    active_incident_id INTEGER
);

CREATE TABLE IF NOT EXISTS incidents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,
    state             TEXT NOT NULL,
    opened_run_id     INTEGER,
    closed_run_id     INTEGER,
    drift_detected_at TEXT NOT NULL,
    verified_at       TEXT,
    mttr_seconds      INTEGER,
    staged            INTEGER NOT NULL DEFAULT 0,
    signals           TEXT,
    summary           TEXT
);

CREATE TABLE IF NOT EXISTS runtime (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def db_path() -> Path:
    env = os.environ.get("SENTINEL_DB")
    return Path(env) if env else DEFAULT_DB


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


# --- runtime key/value (injection state) ------------------------------------


def set_runtime(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO runtime(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def get_runtime(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM runtime WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def clear_runtime(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM runtime WHERE key = ?", (key,))
    conn.commit()


# --- reads ------------------------------------------------------------------


def run_history(conn: sqlite3.Connection, source: str, limit: int = 50) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT ?", (source, limit)
    ).fetchall()
    return list(rows)


def source_state(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM source_state WHERE source = ?", (source,)
    ).fetchone()


def active_incident(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM incidents WHERE source = ? AND verified_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (source,),
    ).fetchone()


def dump_record(row: sqlite3.Row) -> dict:
    return json.loads(row["payload"])
