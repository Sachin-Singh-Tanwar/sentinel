"""ACCEPTANCE A3 — drift is detected, not assumed, and it takes exactly one run."""

from pathlib import Path

from sentinel import db as store
from sentinel.config import get_source
from sentinel.pipeline import inject_drift, run_source

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")


def _run(conn, source, tmp_path):
    return run_source(source, conn, document=LISTING, snapshot_dir=tmp_path / "runs")


def _conn(tmp_path):
    return store.connect(tmp_path / "sentinel.sqlite")


def test_healthy_source_stays_healthy(tmp_path):
    conn = _conn(tmp_path)
    source = get_source("books")

    for _ in range(3):
        result = _run(conn, source, tmp_path)
        assert result["state"] == "HEALTHY"
        assert result["records"] == 20
        assert result["schema_failures"] == 0
        assert result["extractor"] == "books.v1"

    assert store.active_incident(conn, "books") is None


def test_injected_breakage_flips_healthy_to_drift_in_one_run(tmp_path):
    conn = _conn(tmp_path)
    source = get_source("books")

    for _ in range(3):
        assert _run(conn, source, tmp_path)["state"] == "HEALTHY"

    inject_drift(conn, "books")
    result = _run(conn, source, tmp_path)

    assert result["previous_state"] == "HEALTHY"
    assert result["state"] == "DRIFT"
    assert result["staged"] is True
    assert result["records"] == 0
    assert result["signals"]["record_count_drop"]["triggered"] is True

    incident = store.active_incident(conn, "books")
    assert incident is not None
    assert incident["staged"] == 1
    assert incident["state"] == "DRIFT"
    assert incident["opened_run_id"] == result["run_id"]
    assert incident["drift_detected_at"]


def test_a_second_broken_run_does_not_open_a_second_incident(tmp_path):
    conn = _conn(tmp_path)
    source = get_source("books")

    for _ in range(3):
        _run(conn, source, tmp_path)

    inject_drift(conn, "books")
    _run(conn, source, tmp_path)
    second = _run(conn, source, tmp_path)

    count = conn.execute("SELECT COUNT(*) AS n FROM incidents WHERE source='books'").fetchone()["n"]
    assert count == 1
    assert second["incident_id"] == store.active_incident(conn, "books")["id"]


def test_drift_thresholds_come_from_config():
    """Changing the configured threshold changes the verdict without touching code."""
    import copy

    from sentinel.config import load_thresholds
    from sentinel.drift import RunStat, evaluate

    history = [
        RunStat(id=3, records=20, schema_failures=4, required_nulls=0, http_status=200),
        RunStat(id=2, records=20, schema_failures=0, required_nulls=0, http_status=200),
    ]

    config = load_thresholds()
    assert evaluate(history, config).state == "HEALTHY"  # 4/40 = 10%, not > 10%

    strict = copy.deepcopy(config)
    strict["signals"]["schema_fail_rate"]["gt"] = 0.05
    assert evaluate(history, strict).state == "DRIFT"
