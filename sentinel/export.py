"""Static payload builders — SPEC §8 payloads, SPEC §9 screen data, SPEC §14 static demo.

The public demo must load with no API running, so everything the dashboard renders is
produced here as JSON and published to the `data` branch by CI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db as store
from .config import ROOT, load_sources, load_thresholds

LIMITATION = (
    "Repairs are verified against a fixed golden set. A layout the golden set has never "
    "seen can still pass and still be wrong — those cases need a human. Sentinel will not "
    "log in on your behalf, will not bypass bot protection, and will not collect or resell "
    "personal data."
)

STATE_MACHINE = (
    "HEALTHY --drift--> DRIFT --repair--> REPAIRING --gate pass--> VERIFIED --> HEALTHY; "
    "gate fail --> NEEDS_HUMAN"
)


def _json(value: str | None) -> Any:
    return json.loads(value) if value else None


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _elapsed(start: str, end: str | None = None) -> int:
    finish = _parse(end) if end else datetime.now(timezone.utc)
    return max(0, int((finish - _parse(start)).total_seconds()))


def _between(start: str | None, end: str | None) -> float | None:
    """Exact seconds between two timestamps, or None when either is missing."""
    if not start or not end:
        return None
    return round((_parse(end) - _parse(start)).total_seconds(), 3)


def _timing(conn, incident: dict) -> dict[str, float | None]:
    """Split the incident into its two observable phases.

    detection = the run that noticed (fetch + extract + validate + signals)
    repair    = propose + gate + apply, measured from that run finishing
    mttr      = detection + repair, kept in the payload but never shown as one number.
    """
    run = conn.execute(
        "SELECT started_at, finished_at FROM runs WHERE id = ?",
        (incident["opened_run_id"],),
    ).fetchone()
    finished = run["finished_at"] if run else None
    return {
        "detection_seconds": _between(run["started_at"], finished) if run else None,
        "repair_seconds": _between(finished, incident["verified_at"]),
    }


def build_board(conn) -> dict[str, Any]:
    sources = []
    for source in load_sources():
        state = store.source_state(conn, source.id)
        runs = list(
            conn.execute(
                "SELECT id, started_at, records, schema_failures, http_status, staged,"
                " extractor, error FROM runs WHERE source = ? ORDER BY id DESC LIMIT 20",
                (source.id,),
            )
        )
        runs.reverse()
        last = runs[-1] if runs else None
        sources.append(
            {
                "id": source.id,
                "name": source.name,
                "access": source.access,
                "state": state["state"] if state else "UNKNOWN",
                "drift_score": state["drift_score"] if state else None,
                "active_incident": state["active_incident_id"] if state else None,
                "active_extractor": state["active_extractor"] if state else None,
                "last_run": {
                    "id": last["id"],
                    "started_at": last["started_at"],
                    "records": last["records"],
                    "schema_failures": last["schema_failures"],
                    "http_status": last["http_status"],
                    "error": last["error"],
                }
                if last
                else None,
                "sparkline": [run["records"] for run in runs],
            }
        )

    return {
        "generated_at": store.utc_now(),
        "sources": sources,
    }


def build_incident(conn, incident_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    if row is None:
        return None

    incident = dict(row)
    incident["staged"] = bool(incident["staged"])
    incident["signals"] = _json(incident["signals"])
    incident["diff"] = _json(incident["diff"])
    incident["gate_report"] = _json(incident["gate_report"])
    incident["candidate"] = _json(incident["candidate"])

    if incident["mttr_seconds"] is not None:
        incident["duration_seconds"] = incident["mttr_seconds"]
        incident["duration_label"] = "resolved"
    else:
        incident["duration_seconds"] = _elapsed(incident["drift_detected_at"])
        incident["duration_label"] = "ongoing"

    incident.update(_timing(conn, incident))

    last_run = conn.execute(
        "SELECT MAX(id) AS id FROM runs WHERE source = ?", (incident["source"],)
    ).fetchone()["id"]
    upper = incident["closed_run_id"] or last_run or incident["opened_run_id"]
    runs = list(
        conn.execute(
            "SELECT id, started_at, finished_at, records, schema_failures, http_status,"
            " layout_rev, staged, extractor FROM runs"
            " WHERE source = ? AND id BETWEEN ? AND ? ORDER BY id",
            (incident["source"], incident["opened_run_id"], upper),
        )
    )

    timeline: list[dict[str, Any]] = [
        {
            "at": incident["drift_detected_at"],
            "kind": "drift_detected",
            "run_id": incident["opened_run_id"],
            "label": f"drift detected on run #{incident['opened_run_id']}",
        }
    ]
    for run in runs:
        timeline.append(
            {
                "at": run["started_at"],
                "kind": "run",
                "run_id": run["id"],
                "records": run["records"],
                "schema_failures": run["schema_failures"],
                "extractor": run["extractor"],
                "label": f"run #{run['id']}: {run['records']} records",
            }
        )

    if incident["verified_at"]:
        timeline.append(
            {
                "at": incident["verified_at"],
                "kind": "gate_pass",
                "label": (
                    f"gate PASS — {incident['after_version']} applied"
                    f" ({incident['gate_report']['field_accuracy']:.2%} on golden set)"
                ),
            }
        )
    elif incident["state"] == "NEEDS_HUMAN":
        accuracy = (incident["gate_report"] or {}).get("field_accuracy")
        timeline.append(
            {
                "at": incident["drift_detected_at"],
                "kind": "gate_reject",
                "label": "gate REJECT — nothing applied, needs a human"
                + (f" ({accuracy:.2%} on golden set)" if isinstance(accuracy, float) else ""),
            }
        )

    timeline.sort(key=lambda item: item["at"])
    incident["timeline"] = timeline
    incident["runs"] = [dict(run) for run in runs]
    return incident

def build_incidents(conn) -> dict[str, Any]:
    rows = conn.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["staged"] = bool(item["staged"])
        item["signals"] = _json(item["signals"])
        item["diff"] = _json(item["diff"])
        item["gate_report"] = _json(item["gate_report"])
        item["candidate"] = _json(item["candidate"])
        item["duration_seconds"] = (
            item["mttr_seconds"]
            if item["mttr_seconds"] is not None
            else _elapsed(item["drift_detected_at"])
        )
        item["duration_label"] = "resolved" if item["mttr_seconds"] is not None else "ongoing"
        item.update(_timing(conn, item))
        out.append(item)
    return {"generated_at": store.utc_now(), "incidents": out}


def build_method(conn) -> dict[str, Any]:
    import yaml

    thresholds = load_thresholds()
    gate_cfg = yaml.safe_load((ROOT / "config" / "gate.yaml").read_text(encoding="utf-8")) or {}

    conditions = {
        "schema_fail_rate": "schema failures over the last 50 records > 10%",
        "required_null_rate": "required nulls over the last 50 records > 20% and the previous run < 2%",
        "record_count_drop": "records < 40% of the trailing 7-run median",
        "empty_streak": "3 consecutive runs with 0 records",
        "http_fail_streak": "3 consecutive non-2xx responses",
    }

    signals = []
    for name, spec in thresholds["signals"].items():
        signals.append(
            {
                "name": name,
                "condition": conditions.get(name, ""),
                "state": spec["state"],
                "metric": spec["metric"],
            }
        )

    return {
        "generated_at": store.utc_now(),
        "signals": signals,
        "window": thresholds["window"],
        "state_precedence": thresholds["state_precedence"],
        "state_machine": STATE_MACHINE,
        "gate": {
            "field_accuracy_min": gate_cfg.get("field_accuracy_min"),
            "require_zero_regression": gate_cfg.get("require_zero_regression"),
            "decided_by": "the frozen golden set, never the model",
        },
        "limitation": LIMITATION,
    }


def export_all(conn, out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    (out_dir / "incidents").mkdir(parents=True, exist_ok=True)

    board = build_board(conn)
    incidents = build_incidents(conn)
    method = build_method(conn)

    (out_dir / "board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
    (out_dir / "incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
    (out_dir / "method.json").write_text(json.dumps(method, indent=2), encoding="utf-8")

    for item in incidents["incidents"]:
        detail = build_incident(conn, item["id"])
        if detail:
            (out_dir / "incidents" / f"{item['id']}.json").write_text(
                json.dumps(detail, indent=2), encoding="utf-8"
            )

    meta = {
        "generated_at": store.utc_now(),
        "sources": len(board["sources"]),
        "incidents": len(incidents["incidents"]),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
