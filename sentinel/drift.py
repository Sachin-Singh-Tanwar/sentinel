"""Drift evaluation — SPEC §5.

All thresholds come from config/drift.yaml. Nothing numeric is hard-coded here.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .config import load_thresholds


@dataclass
class RunStat:
    id: int
    records: int
    schema_failures: int
    required_nulls: int
    http_status: int | None


@dataclass
class DriftResult:
    state: str
    drift_score: float
    signals: dict[str, dict[str, Any]] = field(default_factory=dict)

    def triggered(self) -> list[str]:
        return [name for name, s in self.signals.items() if s.get("triggered")]


def _window(history: list[RunStat], size: int) -> list[RunStat]:
    """Newest-first history truncated to the last `size` records (not runs)."""
    picked: list[RunStat] = []
    total = 0
    for run in history:
        if total >= size:
            break
        picked.append(run)
        total += run.records
    return picked


def _ratio(values: list[int]) -> float | None:
    denominator = sum(values)
    if denominator <= 0:
        return None
    return sum(values) / denominator


def _trailing(history: list[RunStat], predicate) -> int:
    streak = 0
    for run in history:
        if predicate(run):
            streak += 1
        else:
            break
    return streak


def evaluate(history: list[RunStat], thresholds: dict[str, Any] | None = None) -> DriftResult:
    """Evaluate one source. `history` is newest-first and must include the current run."""
    cfg = thresholds or load_thresholds()
    window_cfg = cfg["window"]
    signals_cfg = cfg["signals"]
    precedence = cfg["state_precedence"]

    if not history:
        return DriftResult(state="HEALTHY", drift_score=0.0, signals={})

    current = history[0]
    recent = _window(history, int(window_cfg["records"]))

    records = sum(r.records for r in recent)
    failures = sum(r.schema_failures for r in recent)
    nulls = sum(r.required_nulls for r in recent)

    schema_fail_rate = (failures / records) if records else None
    required_null_rate = (nulls / records) if records else None

    previous_null_rate = None
    if len(history) > 1:
        prev = history[1]
        if prev.records:
            previous_null_rate = prev.required_nulls / prev.records

    median_window = int(window_cfg["runs_median"])
    prior_counts = [r.records for r in history[1 : median_window + 1]]
    median = statistics.median(prior_counts) if prior_counts else None
    record_count_ratio = (
        current.records / median if median and median > 0 else None
    )

    empty_streak = _trailing(history, lambda r: r.records == 0)
    http_fail_streak = _trailing(
        history,
        # None means "no request was attempted" (offline run); 0 means transport failure.
        lambda r: r.http_status is not None and not (200 <= r.http_status < 300),
    )

    metrics: dict[str, float | int | None] = {
        "schema_fail_rate": schema_fail_rate,
        "required_null_rate": required_null_rate,
        "previous_required_null_rate": previous_null_rate,
        "record_count_ratio": record_count_ratio,
        "empty_streak": empty_streak,
        "http_fail_streak": http_fail_streak,
        "records": records,
    }

    signals: dict[str, dict[str, Any]] = {}

    for name, spec in signals_cfg.items():
        value = metrics.get(spec["metric"])
        triggered = False
        threshold: Any = None

        if value is not None:
            if "gt" in spec:
                threshold = spec["gt"]
                triggered = value > threshold
                if triggered and "previous_lt" in spec:
                    prev = metrics.get("previous_required_null_rate")
                    triggered = prev is not None and prev < spec["previous_lt"]
            elif "lt" in spec:
                threshold = spec["lt"]
                triggered = value < threshold
            elif "gte" in spec:
                threshold = spec["gte"]
                triggered = value >= threshold

        signals[name] = {
            "metric": spec["metric"],
            "value": value,
            "threshold": threshold,
            "state": spec["state"],
            "triggered": triggered,
        }

    triggered_states = [s["state"] for s in signals.values() if s["triggered"]]
    state = "HEALTHY"
    if triggered_states:
        state = min(triggered_states, key=lambda s: precedence.index(s))

    # Drift score is implementation-defined (the SPEC names it but never defines it):
    # the worst continuous severity in [0, 1]. Discrete streaks do not move it.
    candidates = [
        schema_fail_rate or 0.0,
        required_null_rate or 0.0,
    ]
    if record_count_ratio is not None:
        candidates.append(max(0.0, 1.0 - record_count_ratio))
    drift_score = round(min(1.0, max(candidates)), 4)

    return DriftResult(state=state, drift_score=drift_score, signals=signals)


def stats_from_rows(rows) -> list[RunStat]:
    return [
        RunStat(
            id=row["id"],
            records=row["records"],
            schema_failures=row["schema_failures"],
            required_nulls=row["required_nulls"],
            http_status=row["http_status"],
        )
        for row in rows
    ]
