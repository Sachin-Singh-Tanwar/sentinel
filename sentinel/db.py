"""SQLite storage (WAL) — SPEC §12."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
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
    active_incident_id INTEGER,
    active_extractor   TEXT
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
    summary           TEXT,
    before_version    TEXT,
    after_version     TEXT,
    diff              TEXT,
    gate_report       TEXT,
    candidate         TEXT
);

CREATE TABLE IF NOT EXISTS extractor_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    version    TEXT NOT NULL,
    spec       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL,
    notes      TEXT,
    UNIQUE(source, version)
);

CREATE TABLE IF NOT EXISTS runtime (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Columns added after the first deploy; kept here so old databases migrate in place.
MIGRATIONS = {
    "source_state": {"active_extractor": "TEXT"},
    "incidents": {
        "before_version": "TEXT",
        "after_version": "TEXT",
        "diff": "TEXT",
        "gate_report": "TEXT",
        "candidate": "TEXT",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


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
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    conn.commit()


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


# --- extractor versions -----------------------------------------------------


def add_version(
    conn: sqlite3.Connection,
    source: str,
    spec: dict,
    status: str = "candidate",
    notes: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO extractor_versions(source, version, spec, status, created_at, notes)"
        " VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(source, version) DO UPDATE SET spec=excluded.spec,"
        " status=excluded.status, notes=excluded.notes",
        (source, spec["version"], json.dumps(spec, sort_keys=True), status, utc_now(), notes),
    )
    conn.commit()


def active_version(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM extractor_versions WHERE source = ? AND status = 'active'"
        " ORDER BY id DESC LIMIT 1",
        (source,),
    ).fetchone()


def get_version(conn: sqlite3.Connection, source: str, version: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM extractor_versions WHERE source = ? AND version = ?",
        (source, version),
    ).fetchone()


def set_active(conn: sqlite3.Connection, source: str, version: str) -> None:
    conn.execute(
        "UPDATE extractor_versions SET status = 'retired' WHERE source = ? AND status = 'active'",
        (source,),
    )
    conn.execute(
        "UPDATE extractor_versions SET status = 'active' WHERE source = ? AND version = ?",
        (source, version),
    )
    conn.execute(
        "UPDATE source_state SET active_extractor = ? WHERE source = ?", (version, source)
    )
    conn.commit()


def versions(conn: sqlite3.Connection, source: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM extractor_versions WHERE source = ? ORDER BY id", (source,)
        )
    )


# --- reads ------------------------------------------------------------------


def run_history(conn: sqlite3.Connection, source: str, limit: int = 50) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT ?", (source, limit)
        )
    )


def source_state(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM source_state WHERE source = ?", (source,)).fetchone()


def active_incident(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM incidents WHERE source = ? AND verified_at IS NULL"
        " ORDER BY id DESC LIMIT 1",
        (source,),
    ).fetchone()


def records_for_run(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT payload FROM records WHERE run_id = ? ORDER BY idx", (run_id,)
    )
    return [json.loads(row["payload"]) for row in rows]


def dump_record(row: sqlite3.Row) -> dict:
    return json.loads(row["payload"])
