"""Repair loop — SPEC §6 steps 2-5, ACCEPTANCE A4/A5/A6.

propose -> evaluate against the frozen golden set -> gate -> apply or NEEDS_HUMAN.
Nothing is applied on a rejected candidate.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import db as store
from .config import Source
from .factory import build
from .gate import evaluate, field_accuracies
from .propose import propose
from .schema import load_schema


@dataclass
class RepairOutcome:
    applied: bool
    decision: str
    accuracy: float
    incident_id: int
    candidate: dict | None
    report: dict
    diff: dict
    mttr_seconds: int | None = None
    reasons: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "decision": self.decision,
            "accuracy": self.accuracy,
            "incident_id": self.incident_id,
            "candidate_version": (self.candidate or {}).get("version"),
            "report": self.report,
            "diff": self.diff,
            "mttr_seconds": self.mttr_seconds,
            "reasons": self.reasons or [],
        }


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _seconds_between(start: str, end: str) -> int:
    """Whole seconds, rounded up: a resolved incident never reports 0s MTTR."""
    return max(1, math.ceil((_parse(end) - _parse(start)).total_seconds()))


def spec_diff(before: dict, after: dict) -> dict[str, Any]:
    diff: dict[str, Any] = {
        "container": {"before": before.get("container"), "after": after.get("container"),
                      "changed": before.get("container") != after.get("container")},
        "fields": {},
    }
    for name in sorted(set(before.get("fields", {})) | set(after.get("fields", {}))):
        old = before.get("fields", {}).get(name)
        new = after.get("fields", {}).get(name)
        diff["fields"][name] = {
            "before": _selector(old),
            "after": _selector(new),
            "changed": old != new,
        }
    return diff


def _selector(spec: dict | None) -> str | None:
    if not spec:
        return None
    parts = [spec.get("xpath", "")]
    if spec.get("attr"):
        parts.append(f"@{spec['attr']}")
    if spec.get("parse"):
        parts.append(f"parse={spec['parse']}")
    if spec.get("enum_from_class"):
        parts.append("enum_from_class")
    return " ".join(p for p in parts if p)


def attempt_repair(
    source: Source,
    conn,
    golden_records: list[dict],
    *,
    broken_snapshot: Path,
    healthy_snapshot: Path,
    base_url: str | None = None,
) -> RepairOutcome:
    incident = store.active_incident(conn, source.id)
    if incident is None:
        raise RuntimeError(f"no open incident for '{source.id}'")

    from .versions import ensure_active

    incumbent_spec = ensure_active(conn, source)
    schema = load_schema(source.schema_path)
    url = base_url or source.url

    broken_doc = Path(broken_snapshot).read_text(encoding="utf-8")
    healthy_doc = (
        Path(healthy_snapshot).read_text(encoding="utf-8")
        if Path(healthy_snapshot).exists()
        else None
    )

    # What the incumbent could still do on a good page: the bar the candidate must not
    # fall below on any single field.
    baseline = {}
    if healthy_doc:
        healthy_report = evaluate(
            build(incumbent_spec).extract(healthy_doc, url), golden_records, schema
        )
        baseline = field_accuracies(healthy_report)

    candidate_spec = propose(broken_doc, incumbent_spec, url)

    if candidate_spec is None:
        report = {
            "decision": "REJECT",
            "field_accuracy": 0.0,
            "reasons": ["no candidate could be derived from the snapshot"],
        }
        _mark_needs_human(conn, incident, None, report, spec_diff(incumbent_spec, {}))
        return RepairOutcome(
            applied=False,
            decision="REJECT",
            accuracy=0.0,
            incident_id=incident["id"],
            candidate=None,
            report=report,
            diff={},
            reasons=["no candidate"],
        )

    candidate_records = build(candidate_spec).extract(broken_doc, url)
    gate_report = evaluate(
        candidate_records, golden_records, schema, baseline=baseline
    )
    report = gate_report.to_dict()
    diff = spec_diff(incumbent_spec, candidate_spec)

    if not gate_report.passed:
        _mark_needs_human(conn, incident, candidate_spec, report, diff)
        return RepairOutcome(
            applied=False,
            decision="REJECT",
            accuracy=gate_report.field_accuracy,
            incident_id=incident["id"],
            candidate=candidate_spec,
            report=report,
            diff=diff,
            reasons=gate_report.reasons,
        )

    verified_at = store.utc_now()
    mttr = _seconds_between(incident["drift_detected_at"], verified_at)

    store.add_version(
        conn,
        source.id,
        candidate_spec,
        status="candidate",
        notes=f"gate PASS at {gate_report.field_accuracy:.4f}",
    )
    store.set_active(conn, source.id, candidate_spec["version"])

    conn.execute(
        "UPDATE incidents SET state='VERIFIED', verified_at=?, mttr_seconds=?,"
        " before_version=?, after_version=?, diff=?, gate_report=?, candidate=?"
        " WHERE id=?",
        (
            verified_at,
            mttr,
            incumbent_spec["version"],
            candidate_spec["version"],
            json.dumps(diff, sort_keys=True),
            json.dumps(report, sort_keys=True),
            json.dumps(candidate_spec, sort_keys=True),
            incident["id"],
        ),
    )
    conn.execute(
        "UPDATE source_state SET state='VERIFIED', updated_at=?, active_extractor=?"
        " WHERE source=?",
        (verified_at, candidate_spec["version"], source.id),
    )
    conn.commit()

    return RepairOutcome(
        applied=True,
        decision="PASS",
        accuracy=gate_report.field_accuracy,
        incident_id=incident["id"],
        candidate=candidate_spec,
        report=report,
        diff=diff,
        mttr_seconds=mttr,
    )


def _mark_needs_human(conn, incident, candidate_spec, report, diff) -> None:
    conn.execute(
        "UPDATE incidents SET state='NEEDS_HUMAN', gate_report=?, candidate=?, diff=?"
        " WHERE id=?",
        (
            json.dumps(report, sort_keys=True),
            json.dumps(candidate_spec, sort_keys=True) if candidate_spec else None,
            json.dumps(diff, sort_keys=True),
            incident["id"],
        ),
    )
    conn.execute(
        "UPDATE source_state SET state='NEEDS_HUMAN', updated_at=? WHERE source=?",
        (store.utc_now(), incident["source"]),
    )
    conn.commit()


def revert(source: Source, conn, version: str) -> dict:
    """SPEC §6 step 6: any version id can be restored; one command."""
    row = store.get_version(conn, source.id, version)
    if row is None:
        raise RuntimeError(f"unknown version '{version}' for '{source.id}'")

    store.set_active(conn, source.id, version)
    return {"source": source.id, "active": version, "reverted": True}
