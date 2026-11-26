"""Config-defect incidents close without a repair, gate pass, or MTTR."""

from __future__ import annotations

from sentinel import db as store
from sentinel.export import build_incident, build_incidents

REASON = (
    "Closed: our configuration defect, not source drift; no repair was performed. "
    "The stored v1 extractor fields did not match the schema and YAML was never activated."
)


def _seed(conn) -> int:
    cur = conn.execute(
        "INSERT INTO runs(source, started_at, finished_at, http_status, records,"
        " schema_failures, required_nulls, layout_rev, staged, extractor)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("hn", "2026-11-26T11:14:58.836873Z", "2026-11-26T11:15:01.000000Z", 200, 30, 30, 0, 1, 0, "hn.v1"),
    )
    run_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO incidents(source, state, opened_run_id, drift_detected_at, staged, summary)"
        " VALUES(?,?,?,?,?,?)",
        ("hn", "DRIFT", run_id, "2026-11-26T11:14:58.836873Z", 0, None),
    )
    incident_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO source_state(source, state, drift_score, updated_at, last_run_id,"
        " active_incident_id, active_extractor) VALUES(?,?,?,?,?,?,?)",
        ("hn", "DRIFT", 0.5, "2026-11-26T11:14:58.900000Z", run_id, incident_id, "hn.v1"),
    )
    conn.commit()
    return incident_id


def test_config_defect_is_closed_without_repair_or_mttr(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    incident_id = _seed(conn)

    store.close_config_defect(conn, incident_id, 1, REASON)

    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    assert row["state"] == "INVALIDATED"
    assert row["verified_at"] is None
    assert row["mttr_seconds"] is None
    assert row["gate_report"] is None
    assert row["candidate"] is None
    assert row["summary"] == REASON
    assert store.active_incident(conn, "hn") is None
    assert store.source_state(conn, "hn")["active_incident_id"] is None

    detail = build_incident(conn, incident_id)
    assert detail["state"] == "INVALIDATED"
    assert detail["duration_label"] == "invalidated"
    assert detail["duration_seconds"] is None
    assert detail["repair_seconds"] is None
    assert detail["gate_report"] is None
    assert "gate_pass" not in [event["kind"] for event in detail["timeline"]]
    assert any(event["kind"] == "invalidated" for event in detail["timeline"])

    listed = build_incidents(conn)["incidents"][0]
    assert listed["duration_label"] == "invalidated"
    assert listed["mttr_seconds"] is None
    assert listed["verified_at"] is None
    conn.close()
