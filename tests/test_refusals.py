"""ACCEPTANCE A9 — refusals are enforced by the loader, not documented."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from sentinel.config import RefusalError, load_sources

ROOT = Path(__file__).resolve().parent.parent

BASE = {
    "id": "books",
    "name": "books.toscrape.com",
    "access": "html",
    "url": "https://books.toscrape.com/catalogue/page-1.html",
    "schema": "schemas/books.v1.json",
    "golden": "fixtures/books/golden.json",
    "extractor": "books.v1",
}


def _write(tmp_path: Path, **overrides) -> Path:
    entry = {**BASE, **overrides}
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "sources": [entry]}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "overrides",
    [
        {"login": True},
        {"captcha": "solve"},
        {"auth": {"username": "someone"}},
        {"proxy_rotation": True},
        {"cookies": {"session": "abc"}},
    ],
)
def test_loader_refuses_protected_sources(tmp_path, overrides):
    path = _write(tmp_path, **overrides)
    with pytest.raises(RefusalError):
        load_sources(path)


def test_loader_accepts_a_plain_public_source(tmp_path):
    path = _write(tmp_path)
    assert [s.id for s in load_sources(path)] == ["books"]


@pytest.mark.parametrize("overrides", [{"login": True}, {"captcha": "solve"}])
def test_cli_exits_non_zero_on_refused_config(tmp_path, overrides):
    config = _write(tmp_path, **overrides)
    env = {
        **os.environ,
        "SENTINEL_SOURCES": str(config),
        "SENTINEL_DB": str(tmp_path / "db.sqlite"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "sentinel.cli", "state"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "refused" in result.stderr.lower()
