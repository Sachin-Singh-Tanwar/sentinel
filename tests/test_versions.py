"""Extractor version integrity: config is data, but it must not rewrite a stored spec."""

from __future__ import annotations

from dataclasses import replace

from sentinel import db as store
from sentinel import versions
from sentinel.config import get_source


def _hn_spec(version: str, fields: dict) -> dict:
    return {
        "version": version,
        "notes": f"test spec {version}",
        "container": "//tr[contains(@class,'athing')]",
        "fields": fields,
    }


def _seed(conn, spec: dict) -> None:
    store.add_version(conn, "hn", spec, status="active", notes=spec.get("notes"))


def test_same_version_spec_change_is_rejected(tmp_path, monkeypatch):
    """A v1 row with old fields must not be silently rewritten by an edited v1 YAML."""
    conn = store.connect(tmp_path / "db.sqlite")
    stored = _hn_spec(
        "hn.v1",
        {
            "rank": {"xpath": ".//span[@class='rank']", "parse": "money"},
            "title": {"xpath": ".//span[@class='titleline']/a"},
            "url": {"xpath": ".//span[@class='titleline']/a", "attr": "href"},
        },
    )
    _seed(conn, stored)

    edited = _hn_spec(
        "hn.v1",
        {
            "title": {"xpath": ".//span[contains(@class,'titleline')]/a"},
            "url": {"xpath": ".//span[contains(@class,'titleline')]/a", "attr": "href"},
            "rank": {"xpath": ".//span[contains(@class,'rank')]", "parse": "money"},
            "points": {"xpath": ".//span[contains(@class,'score')]", "parse": "money"},
        },
    )
    monkeypatch.setattr(versions, "config_versions", lambda source: [edited])

    try:
        versions.ensure_active(conn, replace(get_source("hn"), extractor="hn.v1"))
    except RuntimeError as exc:
        assert "hn.v1" in str(exc)
    else:
        raise AssertionError("same-version spec change was accepted silently")
    finally:
        conn.close()


def test_new_config_version_is_activated_and_old_row_retired(tmp_path, monkeypatch):
    conn = store.connect(tmp_path / "db.sqlite")
    _seed(conn, _hn_spec("hn.v1", {"title": {"xpath": "a"}, "url": {"xpath": "a"}}))

    upgraded = _hn_spec(
        "hn.v2",
        {
            "title": {"xpath": ".//span[contains(@class,'titleline')]/a"},
            "url": {"xpath": ".//span[contains(@class,'titleline')]/a", "attr": "href"},
            "rank": {"xpath": ".//span[contains(@class,'rank')]", "parse": "money"},
        },
    )
    monkeypatch.setattr(versions, "config_versions", lambda source: [upgraded])

    try:
        active = versions.ensure_active(conn, get_source("hn"))
        assert active["version"] == "hn.v2"
        assert store.active_version(conn, "hn")["version"] == "hn.v2"
        assert store.get_version(conn, "hn", "hn.v1")["status"] == "retired"
    finally:
        conn.close()
