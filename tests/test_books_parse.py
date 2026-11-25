"""books.v1 parsing against a saved copy of the real page."""

from pathlib import Path

from sentinel.extractors.books import BooksV1
from sentinel.schema import load_schema, validate_record

ROOT = Path(__file__).resolve().parent.parent
LISTING = (ROOT / "tests" / "fixtures" / "books_listing.html").read_text(encoding="utf-8")
DETAIL = (ROOT / "tests" / "fixtures" / "books_detail.html").read_text(encoding="utf-8")
SCHEMA = load_schema(ROOT / "schemas" / "books.v1.json")


def test_listing_yields_twenty_books():
    records = BooksV1().parse_listing(LISTING, "https://books.toscrape.com/catalogue/page-1.html")
    assert len(records) == 20


def test_fields_are_typed_before_detail_enrichment():
    records = BooksV1().parse_listing(LISTING, "https://books.toscrape.com/catalogue/page-1.html")
    first = records[0]

    assert isinstance(first["title"], str) and first["title"]
    assert isinstance(first["price"], float)
    assert first["rating"] in {"One", "Two", "Three", "Four", "Five"}
    assert first["url"].startswith("https://books.toscrape.com/")
    # stock only exists on the detail page — see the module docstring
    assert first["stock"] is None


def test_detail_page_carries_the_stock_count():
    assert BooksV1().parse_detail(DETAIL) == 22


def test_full_extraction_passes_the_schema():
    records = BooksV1().extract(LISTING, "https://books.toscrape.com/catalogue/page-1.html", lambda url: DETAIL)
    assert len(records) == 20
    for record in records:
        validation = validate_record(record, SCHEMA)
        assert validation.ok, validation.errors
        assert record["stock"] == 22


def test_prices_are_numbers_not_strings():
    records = BooksV1().parse_listing(LISTING, "https://books.toscrape.com/catalogue/page-1.html")
    assert all(isinstance(r["price"], float) for r in records)
