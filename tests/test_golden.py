"""SPEC §4 + ACCEPTANCE anti-gaming — the golden set is frozen, never rewritten."""

import json
from pathlib import Path

import pytest

from sentinel import golden
from sentinel.config import Source


def _source(tmp_path: Path) -> Source:
    return Source(
        id="books",
        name="books.toscrape.com",
        access="html",
        url="https://example.test/page-1.html",
        schema_path=Path(__file__).resolve().parent.parent / "schemas" / "books.v1.json",
        golden_path=tmp_path / "golden.json",
        extractor="books.v1",
    )


def _record(index: int) -> dict:
    return {
        "title": f"Book {index}",
        "price": 10.0 + index,
        "rating": "Three",
        "stock": 5,
        "url": f"https://example.test/book-{index}.html",
    }


def _write_golden(path: Path, count: int = 20) -> None:
    path.write_text(json.dumps({"records": [_record(i) for i in range(count)]}), encoding="utf-8")


def test_missing_golden_is_an_error_not_an_empty_set(tmp_path):
    with pytest.raises(golden.GoldenMissing):
        golden.load(_source(tmp_path))


def test_wrong_size_golden_is_rejected(tmp_path):
    source = _source(tmp_path)
    _write_golden(source.golden_path, count=19)
    with pytest.raises(golden.GoldenInvalid):
        golden.load(source)


def test_golden_records_must_satisfy_the_schema(tmp_path):
    source = _source(tmp_path)
    payload = {"records": [_record(i) for i in range(20)]}
    payload["records"][3]["rating"] = "Six"
    source.golden_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(golden.GoldenInvalid):
        golden.load(source)


def test_guard_detects_a_mutated_golden_file(tmp_path):
    source = _source(tmp_path)
    _write_golden(source.golden_path)

    with pytest.raises(golden.GoldenMutated):
        with golden.guard(source):
            source.golden_path.write_text(json.dumps({"records": []}), encoding="utf-8")


def test_guard_is_silent_when_the_file_is_untouched(tmp_path):
    source = _source(tmp_path)
    _write_golden(source.golden_path)

    with golden.guard(source) as digest:
        assert digest == golden.sha256_of(source.golden_path)


def test_load_does_not_touch_the_file(tmp_path):
    source = _source(tmp_path)
    _write_golden(source.golden_path)

    before_sha = golden.sha256_of(source.golden_path)
    before_mtime = source.golden_path.stat().st_mtime_ns

    golden.load(source)

    assert golden.sha256_of(source.golden_path) == before_sha
    assert source.golden_path.stat().st_mtime_ns == before_mtime
