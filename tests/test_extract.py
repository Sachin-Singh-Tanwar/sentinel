"""Extraction + golden-set reproduction.

The golden set was captured once by scripts/capture_golden.py (regex, independent of
the engine) and sealed. These tests prove the shipped extractor reproduces it exactly.
"""

from pathlib import Path

import yaml

from sentinel import golden
from sentinel.config import get_source
from sentinel.engine import Extractor
from sentinel.schema import load_schema, validate_record

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")
SCHEMA = load_schema(ROOT / "schemas" / "books.v1.json")
SPEC = yaml.safe_load((ROOT / "config" / "extractors" / "books.yaml").read_text(encoding="utf-8"))["versions"][0]


def _records() -> list[dict]:
    return Extractor(SPEC).extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html")


def test_listing_yields_twenty_books():
    assert len(_records()) == 20


def test_required_fields_are_typed():
    first = _records()[0]
    assert isinstance(first["title"], str) and first["title"]
    assert isinstance(first["price"], float)
    assert first["rating"] in {"One", "Two", "Three", "Four", "Five"}
    assert first["url"].startswith("https://books.toscrape.com/catalogue/")
    assert first["stock"] is None  # the listing page does not publish counts


def test_every_record_passes_the_schema():
    for record in _records():
        assert validate_record(record, SCHEMA).ok


def test_extractor_reproduces_the_golden_set_exactly():
    source = get_source("books")
    gs = golden.load(source)
    assert len(gs) == 20

    produced = _records()
    assert len(produced) == len(gs.records)
    for expected, actual in zip(gs.records, produced):
        for name in ("title", "price", "rating", "url"):
            assert actual[name] == expected[name], f"{name}: {actual[name]!r} != {expected[name]!r}"


def test_golden_set_is_sealed_and_unmodified():
    source = get_source("books")
    gs = golden.load(source)
    golden.verify_seal(source, gs)
    assert golden.fingerprint_file(source).exists()
