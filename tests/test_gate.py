"""ACCEPTANCE A4 (reject a wrong repair) and A5 (accept a correct one)."""

from pathlib import Path

import pytest
import yaml

from sentinel import golden
from sentinel.config import get_source
from sentinel.engine import Extractor
from sentinel.gate import evaluate, field_accuracies
from sentinel.schema import load_schema

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")
SCHEMA = load_schema(ROOT / "schemas" / "books.v1.json")
SPEC = yaml.safe_load((ROOT / "config" / "extractors" / "books.yaml").read_text(encoding="utf-8"))["versions"][0]


@pytest.fixture(scope="module")
def golden_records():
    return golden.load(get_source("books")).records


def test_known_good_candidate_passes(golden_records):
    report = evaluate(Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html"), golden_records, SCHEMA)

    assert report.decision == "PASS"
    assert report.field_accuracy == 1.0
    assert all(score.correct == score.total == 20 for score in report.fields.values())


def test_broken_candidate_is_rejected(golden_records):
    broken = []
    for record in Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html"):
        broken.append({**record, "price": None, "rating": None})

    report = evaluate(broken, golden_records, SCHEMA)

    assert report.decision == "REJECT"
    assert report.field_accuracy < 0.95
    assert any("field_accuracy" in reason for reason in report.reasons)


def test_a_regression_rejects_even_above_threshold(golden_records):
    """Everything right except `rating`, which used to be perfect -> regression."""
    damaged = []
    for record in Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html"):
        damaged.append({**record, "rating": None})

    baseline = {"title": 1.0, "price": 1.0, "url": 1.0, "rating": 1.0, "stock": 1.0}
    report = evaluate(damaged, golden_records, SCHEMA, baseline=baseline)

    # 80 of 100 field values are correct, which is below 0.95 anyway, but the point is
    # that the regression is named explicitly rather than hidden in the average.
    assert report.decision == "REJECT"
    assert [r["field"] for r in report.regressions] == ["rating"]


def test_missing_records_count_as_wrong_values(golden_records):
    truncated = Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html")[:10]
    report = evaluate(truncated, golden_records, SCHEMA)

    assert report.decision == "REJECT"
    assert report.records_found == 10
    assert report.field_accuracy == pytest.approx(0.5)


def test_baseline_is_per_field_not_a_single_number(golden_records):
    good = evaluate(Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html"), golden_records, SCHEMA)
    assert field_accuracies(good)["title"] == 1.0
