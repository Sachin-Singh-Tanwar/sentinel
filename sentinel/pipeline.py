"""One run of one source: fetch -> snapshot -> extract -> validate -> drift -> state.

SPEC §6 step 1 (capture) and §7 (states) live here.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import db as store
from .config import Source
from .drift import DriftResult, evaluate, stats_from_rows
from .extractors import get_extractor
from .fetch import fetch_text, mutate_layout, new_client
from .schema import load_schema, validate_many

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "var" / "runs"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def injected_rev(conn: sqlite3.Connection, source_id: str) -> int:
    return int(store.get_runtime(conn, f"inject:{source_id}", "1") or 1)


def run_source(
    source: Source,
    conn: sqlite3.Connection,
    *,
    document: str | None = None,
    detail_fetcher: Callable[[str], str | None] | None = None,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute one run. `document`/`detail_fetcher` exist so tests can stay offline."""
    rev = injected_rev(conn, source.id)
    staged = rev != 1
    extractor = get_extractor(source.extractor)
    schema = load_schema(source.schema_path)

    started_at = utc_now()
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

    if detail_fetcher is None and client is not None and listing is not None:
        def detail_fetcher(url: str) -> str | None:  # noqa: F811
            try:
                status, text = fetch_text(client, url)
            except Exception:
                return None
            if not (200 <= status < 300):
                return None
            return mutate_layout(text, rev)

    records: list[dict] = []
    validations = []
    if listing is not None and error is None:
        try:
            records = extractor.extract(listing, source.url, detail_fetcher)
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
            source.extractor,
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
        snapshot_path = str(file_path.relative_to(ROOT)) if file_path.is_relative_to(ROOT) else str(file_path)
        conn.execute("UPDATE runs SET snapshot = ? WHERE id = ?", (snapshot_path, run_id))

    conn.execute("UPDATE runs SET finished_at = ? WHERE id = ?", (utc_now(), run_id))
    conn.commit()

    history = stats_from_rows(store.run_history(conn, source.id, limit=50))
    drift = evaluate(history)

    previous = store.source_state(conn, source.id)
    previous_state = previous["state"] if previous else None

    incident = store.active_incident(conn, source.id)
    incident_id = incident["id"] if incident else None

    if drift.state != "HEALTHY" and incident_id is None and previous_state in (None, "HEALTHY"):
        cur = conn.execute(
            "INSERT INTO incidents(source, state, opened_run_id, drift_detected_at, staged, signals)"
            " VALUES(?,?,?,?,?,?)",
            (
                source.id,
                drift.state,
                run_id,
                started_at,
                int(staged),
                json.dumps(drift.signals, sort_keys=True),
            ),
        )
        incident_id = int(cur.lastrowid)

    conn.execute(
        "INSERT INTO source_state(source, state, drift_score, updated_at, last_run_id,"
        " active_incident_id) VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(source) DO UPDATE SET state=excluded.state,"
        " drift_score=excluded.drift_score, updated_at=excluded.updated_at,"
        " last_run_id=excluded.last_run_id, active_incident_id=excluded.active_incident_id",
        (source.id, drift.state, drift.drift_score, utc_now(), run_id, incident_id),
    )
    conn.commit()

    return {
        "run_id": run_id,
        "source": source.id,
        "state": drift.state,
        "previous_state": previous_state,
        "drift_score": drift.drift_score,
        "records": len(records),
        "schema_failures": schema_failures,
        "required_nulls": required_nulls,
        "http_status": http_status,
        "layout_rev": rev,
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
