"""The gate — SPEC §6 step 4, ACCEPTANCE A4/A5.

A repair passes only if it reproduces the golden set: field accuracy >= 0.95 AND no
field that used to pass now fails. Nothing here looks at how confident anyone is.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
GATE_PATH = Path(os.environ.get("SENTINEL_GATE", ROOT / "config" / "gate.yaml"))

EPSILON = 1e-9


def load_gate(path: Path | str | None = None) -> dict[str, Any]:
    target = Path(path) if path else GATE_PATH
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


@dataclass
class FieldScore:
    correct: int = 0
    total: int = 0
    null_in_golden: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class GateReport:
    decision: str
    field_accuracy: float
    threshold: float
    records_expected: int
    records_found: int
    fields: dict[str, FieldScore] = field(default_factory=dict)
    regressions: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fields"] = {
            name: {
                "correct": score.correct,
                "total": score.total,
                "accuracy": round(score.accuracy, 4),
                "null_in_golden": score.null_in_golden,
            }
            for name, score in self.fields.items()
        }
        return payload

    @property
    def passed(self) -> bool:
        return self.decision == "PASS"


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= EPSILON
    return left == right


def evaluate(
    candidate: list[dict],
    golden: list[dict],
    schema: dict,
    *,
    baseline: dict[str, float] | None = None,
    gate: dict[str, Any] | None = None,
) -> GateReport:
    """Score `candidate` against the frozen golden records, field by field."""
    cfg = gate or load_gate()
    threshold = float(cfg.get("field_accuracy_min", 0.95))
    require_zero_regression = bool(cfg.get("require_zero_regression", True))

    names = list(schema["fields"])
    scores = {name: FieldScore() for name in names}

    for index, expected in enumerate(golden):
        present = index < len(candidate)
        found = candidate[index] if present else {}
        for name in names:
            scores[name].total += 1
            if expected.get(name) is None:
                scores[name].null_in_golden += 1
            # A record that is missing entirely scores zero on every field — it must not
            # get credit for fields where the golden value happens to be null.
            if present and name in expected and _equal(found.get(name), expected.get(name)):
                scores[name].correct += 1

    correct = sum(s.correct for s in scores.values())
    total = sum(s.total for s in scores.values())
    accuracy = correct / total if total else 0.0

    regressions: list[dict[str, Any]] = []
    if require_zero_regression and baseline:
        for name, score in scores.items():
            previous = float(baseline.get(name, 0.0))
            if score.accuracy + EPSILON < previous:
                regressions.append(
                    {
                        "field": name,
                        "was": round(previous, 4),
                        "now": round(score.accuracy, 4),
                    }
                )

    reasons: list[str] = []
    if accuracy + EPSILON < threshold:
        reasons.append(f"field_accuracy {accuracy:.4f} < {threshold:.2f}")
    if regressions:
        reasons.append(
            "regressed fields: " + ", ".join(r["field"] for r in regressions)
        )
    if not candidate:
        reasons.append("candidate extracted 0 records")

    decision = "REJECT" if reasons else "PASS"

    return GateReport(
        decision=decision,
        field_accuracy=round(accuracy, 6),
        threshold=threshold,
        records_expected=len(golden),
        records_found=len(candidate),
        fields=scores,
        regressions=regressions,
        reasons=reasons,
    )


def field_accuracies(report: GateReport) -> dict[str, float]:
    return {name: round(score.accuracy, 6) for name, score in report.fields.items()}
