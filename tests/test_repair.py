"""ACCEPTANCE A4/A5/A6/A7 — repair applies only through the gate, and reverts cleanly."""

import json
from pathlib import Path

import pytest

from sentinel import db as store
from sentinel import golden
from sentinel.config import get_source
from sentinel.pipeline import (
    clear_injection,
    healthy_snapshot_path,
    inject_drift,
    run_source,
)
from sentinel.repair import attempt_repair, revert

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")


def _drifted(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    source = get_source("books")
    run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")
    inject_drift(conn, "books")
    broken = run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")
    assert broken["state"] == "DRIFT"
    return conn, source, broken


def _repair(conn, source, broken):
    return attempt_repair(
        source,
        conn,
        golden.load(source).records,
        broken_snapshot=ROOT / broken["snapshot"],
        healthy_snapshot=healthy_snapshot_path(source.id),
    )


def test_good_candidate_is_applied_and_verified(tmp_path):
    conn, source, broken = _drifted(tmp_path)
    before_mtime = golden.load(source).mtime_ns

    outcome = _repair(conn, source, broken)

    assert outcome.applied is True
    assert outcome.decision == "PASS"
    assert outcome.accuracy == 1.0
    assert outcome.candidate["version"] == "books.v2"
    assert outcome.mttr_seconds >= 1

    incident = conn.execute("SELECT * FROM incidents WHERE id = ?", (outcome.incident_id,)).fetchone()
    assert incident["state"] == "VERIFIED"
    assert incident["verified_at"]
    assert incident["mttr_seconds"] == outcome.mttr_seconds
    assert incident["before_version"] == "books.v1"
    assert incident["after_version"] == "books.v2"
    assert json.loads(incident["diff"])["container"]["changed"] is True

    assert store.active_version(conn, "books")["version"] == "books.v2"
    # anti-gaming: the golden file is byte- and mtime-identical after a repair
    assert golden.load(source).mtime_ns == before_mtime


def test_repair_then_run_reaches_healthy(tmp_path):
    conn, source, broken = _drifted(tmp_path)
    _repair(conn, source, broken)

    after = run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")

    assert after["previous_state"] == "VERIFIED"
    assert after["state"] == "HEALTHY"
    assert after["records"] == 20
    assert after["extractor"] == "books.v2"


def test_broken_candidate_is_rejected_and_nothing_is_applied(tmp_path, monkeypatch):
    conn, source, broken = _drifted(tmp_path)

    bad_spec = {
        "version": "books.v9",
        "container": "//article[contains(@class,'product_card')]",
        "fields": {
            "title": {"xpath": ".//a[@title]", "attr": "title"},
            "url": {"xpath": ".//a[@title]", "attr": "href", "absolute": True},
        },
    }
    monkeypatch.setattr("sentinel.repair.propose", lambda *a, **k: bad_spec)

    outcome = _repair(conn, source, broken)

    assert outcome.applied is False
    assert outcome.decision == "REJECT"
    assert outcome.accuracy < 0.95

    incident = conn.execute("SELECT * FROM incidents WHERE id = ?", (outcome.incident_id,)).fetchone()
    assert incident["state"] == "NEEDS_HUMAN"
    assert incident["verified_at"] is None
    assert incident["mttr_seconds"] is None
    assert json.loads(incident["candidate"])["version"] == "books.v9"

    # nothing applied
    assert store.active_version(conn, "books")["version"] == "books.v1"
    assert store.get_version(conn, "books", "books.v9") is None


def test_revert_restores_the_previous_extractor_and_reproduces_golden(tmp_path):
    conn, source, broken = _drifted(tmp_path)
    _repair(conn, source, broken)
    assert store.active_version(conn, "books")["version"] == "books.v2"

    clear_injection(conn, "books")
    revert(source, conn, "books.v1")

    assert store.active_version(conn, "books")["version"] == "books.v1"

    result = run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")
    assert result["records"] == 20
    assert result["schema_failures"] == 0
    assert result["state"] == "HEALTHY"

    produced = store.records_for_run(conn, result["run_id"])
    expected = golden.load(source).records
    assert len(produced) == 20
    for want, got in zip(expected, produced):
        for name in ("title", "price", "rating", "url"):
            assert got[name] == want[name]


def test_repair_without_an_open_incident_is_an_error(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    source = get_source("books")

    with pytest.raises(RuntimeError):
        attempt_repair(
            source,
            conn,
            golden.load(source).records,
            broken_snapshot=ROOT / "tests" / "fixtures" / "books_listing.html",
            healthy_snapshot=ROOT / "tests" / "fixtures" / "books_listing.html",
        )
