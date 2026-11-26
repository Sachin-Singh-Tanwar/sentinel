"""One run of one source: fetch -> snapshot -> extract -> validate -> drift -> state.

SPEC §6 step 1 (capture) and §7 (states) live here.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Callable

from . import db as store
from .config import Source
from .drift import evaluate, stats_from_rows
from .factory import build
from .fetch import fetch_text, mutate_layout, new_client
from .schema import load_schema, validate_many
from .versions import ensure_active

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "var" / "runs"
HEALTHY_DIR = ROOT / "var" / "snapshots"


def injected_rev(conn: sqlite3.Connection, source_id: str) -> int:
    return int(store.get_runtime(conn, f"inject:{source_id}", "1") or 1)


def healthy_snapshot_path(source_id: str) -> Path:
    return HEALTHY_DIR / source_id / "last-healthy.html"


def run_source(
    source: Source,
    conn: sqlite3.Connection,
    *,
    document: str | None = None,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute one run. `document` exists so tests can stay offline."""
    rev = injected_rev(conn, source.id)
    staged = rev != 1
    spec = ensure_active(conn, source)
    extractor = build(spec)
    schema = load_schema(source.schema_path)

    started_at = store.utc_now()
    http_status: int | None = None
    error: str | None = None
    listing = document
    client = None

    if listing is not None:
        http_status = 200  # caller-supplied document: no request was made
    else:
        client = new_client()
        try:
            http_status, listing = fetch_text(client, source.url)
        except Exception as exc:  # network failure is a signal, not a crash
            http_status = 0  # 0 = transport failure, distinct from "not attempted"
            error = f"{type(exc).__name__}: {exc}"

    if listing is not None:
        listing = mutate_layout(listing, rev)

    records: list[dict] = []
    validations = []
    if listing is not None and error is None:
        try:
            records = extractor.extract(listing, source.url)
            validations = validate_many(records, schema)
        except Exception as exc:
            error = f"extract failed: {type(exc).__name__}: {exc}"
            records, validations = [], []

    if client is not None:
        client.close()

    schema_failures = sum(1 for v in validations if not v.ok)
    required_nulls = sum(1 for v in validations if v.required_null_fields)

    cur = conn.execute(
        "INSERT INTO runs(source, started_at, http_status, records, schema_failures,"
        " required_nulls, layout_rev, staged, extractor, error)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            source.id,
            started_at,
            http_status,
            len(records),
            schema_failures,
            required_nulls,
            rev,
            int(staged),
            spec["version"],
            error,
        ),
    )
    run_id = int(cur.lastrowid)

    for idx, record in enumerate(records):
        conn.execute(
            "INSERT INTO records(run_id, idx, payload, valid) VALUES(?,?,?,?)",
            (run_id, idx, json.dumps(record, sort_keys=True), int(validations[idx].ok)),
        )

    snapshot_path = None
    if listing is not None:
        target = (snapshot_dir or RUNS_DIR) / str(run_id)
        target.mkdir(parents=True, exist_ok=True)
        file_path = target / "snapshot.html"
        file_path.write_text(listing, encoding="utf-8")
        try:
            snapshot_path = str(file_path.relative_to(ROOT))
        except ValueError:
            snapshot_path = str(file_path)
        conn.execute("UPDATE runs SET snapshot = ? WHERE id = ?", (snapshot_path, run_id))

    conn.execute("UPDATE runs SET finished_at = ? WHERE id = ?", (store.utc_now(), run_id))
    conn.commit()

    history = stats_from_rows(store.run_history(conn, source.id, limit=50))
    drift = evaluate(history)

    previous = store.source_state(conn, source.id)
    previous_state = previous["state"] if previous else None

    # SPEC §7: VERIFIED -> HEALTHY on the first clean run after a gated repair.
    new_state = drift.state
    if drift.state == "HEALTHY" and previous_state == "VERIFIED":
        new_state = "HEALTHY"

    incident = store.active_incident(conn, source.id)
    incident_id = incident["id"] if incident else None

    if new_state != "HEALTHY" and incident_id is None and previous_state in (None, "HEALTHY"):
        cur = conn.execute(
            "INSERT INTO incidents(source, state, opened_run_id, drift_detected_at, staged, signals)"
            " VALUES(?,?,?,?,?,?)",
            (
                source.id,
                new_state,
                run_id,
                started_at,
                int(staged),
                json.dumps(drift.signals, sort_keys=True),
            ),
        )
        incident_id = int(cur.lastrowid)

    if new_state == "HEALTHY" and incident is not None and incident["verified_at"]:
        conn.execute(
            "UPDATE incidents SET closed_run_id = ? WHERE id = ?", (run_id, incident["id"])
        )
        incident_id = incident["id"]

    conn.execute(
        "INSERT INTO source_state(source, state, drift_score, updated_at, last_run_id,"
        " active_incident_id, active_extractor) VALUES(?,?,?,?,?,?,?)"
        " ON CONFLICT(source) DO UPDATE SET state=excluded.state,"
        " drift_score=excluded.drift_score, updated_at=excluded.updated_at,"
        " last_run_id=excluded.last_run_id, active_incident_id=excluded.active_incident_id,"
        " active_extractor=excluded.active_extractor",
        (
            source.id,
            new_state,
            drift.drift_score,
            store.utc_now(),
            run_id,
            incident_id,
            spec["version"],
        ),
    )
    conn.commit()

    if new_state == "HEALTHY" and listing is not None:
        keep = healthy_snapshot_path(source.id)
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(listing, encoding="utf-8")

    return {
        "run_id": run_id,
        "source": source.id,
        "state": new_state,
        "previous_state": previous_state,
        "drift_score": drift.drift_score,
        "records": len(records),
        "schema_failures": schema_failures,
        "required_nulls": required_nulls,
        "http_status": http_status,
        "layout_rev": rev,
        "extractor": spec["version"],
        "staged": staged,
        "incident_id": incident_id,
        "signals": drift.signals,
        "snapshot": snapshot_path,
        "error": error,
    }


def inject_drift(conn: sqlite3.Connection, source_id: str, rev: int = 2) -> None:
    """Break one source deliberately. Every incident opened while this is active is staged."""
    store.set_runtime(conn, f"inject:{source_id}", str(rev))


def clear_injection(conn: sqlite3.Connection, source_id: str) -> None:
    store.clear_runtime(conn, f"inject:{source_id}")
