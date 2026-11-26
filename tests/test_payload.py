"""ACCEPTANCE A7/A8 payload side — /incidents/:id carries diff, golden report, MTTR, staged."""

import json
from pathlib import Path

import pytest

from sentinel import db as store
from sentinel import golden
from sentinel.config import get_source
from sentinel.export import build_incident, build_incidents, export_all
from sentinel.pipeline import healthy_snapshot_path, inject_drift, run_source
from sentinel.repair import attempt_repair

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")


def _resolved(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    source = get_source("books")
    run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")
    inject_drift(conn, "books")
    broken = run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")
    outcome = attempt_repair(
        source,
        conn,
        golden.load(source).records,
        broken_snapshot=ROOT / broken["snapshot"],
        healthy_snapshot=healthy_snapshot_path(source.id),
    )
    return conn, outcome.incident_id


def test_incident_payload_has_everything_the_ui_needs(tmp_path):
    conn, incident_id = _resolved(tmp_path)
    payload = build_incident(conn, incident_id)

    assert payload["staged"] is True
    assert payload["state"] == "VERIFIED"
    assert payload["mttr_seconds"] > 0
    assert payload["before_version"] == "books.v1"
    assert payload["after_version"] == "books.v2"

    assert payload["diff"]["container"]["before"] == "//article[contains(@class,'product_pod')]"
    assert payload["diff"]["container"]["after"] == "//article[contains(@class,'product_card')]"
    assert payload["diff"]["container"]["changed"] is True

    report = payload["gate_report"]
    assert report["decision"] == "PASS"
    assert report["field_accuracy"] == 1.0
    assert report["records_found"] == report["records_expected"] == 20
    for field in ("title", "price", "url"):
        assert report["fields"][field]["correct"] == 20
        assert report["fields"][field]["total"] == 20

    kinds = [event["kind"] for event in payload["timeline"]]
    assert "drift_detected" in kinds
    assert "gate_pass" in kinds


def test_timing_is_split_into_detection_and_repair(tmp_path):
    conn, incident_id = _resolved(tmp_path)
    payload = build_incident(conn, incident_id)

    assert payload["detection_seconds"] > 0
    assert payload["repair_seconds"] > 0
    # MTTR stays in the payload for the API contract, but it is the two phases
    # added together — the UI reports the phases, not the rounded total.
    assert payload["detection_seconds"] + payload["repair_seconds"] == pytest.approx(
        payload["mttr_seconds"], abs=1.0
    )

    listed = build_incidents(conn)["incidents"][0]
    assert listed["detection_seconds"] == payload["detection_seconds"]
    assert listed["repair_seconds"] == payload["repair_seconds"]


def test_static_export_is_self_contained(tmp_path):
    conn, _ = _resolved(tmp_path)
    out = tmp_path / "data"
    meta = export_all(conn, out)

    assert meta["incidents"] == 1
    for name in ("board.json", "incidents.json", "method.json", "meta.json"):
        assert (out / name).exists(), name
    assert (out / "incidents" / "1.json").exists()

    method = json.loads((out / "method.json").read_text(encoding="utf-8"))
    assert "golden set has never seen" in method["limitation"]
    assert len(method["signals"]) == 5

    board = json.loads((out / "board.json").read_text(encoding="utf-8"))
    assert board["sources"][0]["id"] == "books"
