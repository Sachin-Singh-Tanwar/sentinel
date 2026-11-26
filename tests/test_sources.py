"""ACCEPTANCE A1 — five sources configured, none require auth.

Also covers the JSON extractor and the dispatch that keeps step 5 config-only:
adding a source is a YAML entry, never a new parser branch.
"""

from pathlib import Path

import yaml

from sentinel.config import load_sources
from sentinel.engine import Extractor
from sentinel.factory import build
from sentinel.json_engine import JsonExtractor
from sentinel.schema import load_schema, validate_many

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "sources.yaml"

EXPECTED = ["books", "hn", "gh", "apify", "remoteok"]


def _entries() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["sources"]


def test_five_sources_are_configured():
    sources = load_sources()
    assert [s.id for s in sources] == EXPECTED


def test_no_source_declares_auth_login_or_captcha():
    for entry in _entries():
        assert not entry.get("auth"), entry["id"]
        assert entry.get("login") is not True, entry["id"]
        assert entry.get("captcha") in (None, "none", False), entry["id"]
        assert not entry.get("proxy"), entry["id"]
        assert entry.get("proxy_rotation") is not True, entry["id"]


def test_every_source_has_a_schema_and_a_versioned_extractor():
    for source in load_sources():
        assert source.schema_path.exists(), source.id
        assert source.extractor.startswith(source.id + ".v"), source.id
        versions = yaml.safe_load(
            (ROOT / "config" / "extractors" / f"{source.id}.yaml").read_text(encoding="utf-8")
        )["versions"]
        assert any(v["version"] == source.extractor for v in versions), source.id


# --- the JSON engine --------------------------------------------------------

GITHUB = """
{
  "total_count": 2,
  "items": [
    {"full_name": "a/one", "stargazers_count": 120000, "html_url": "https://github.com/a/one", "language": "Go"},
    {"full_name": "b/two", "stargazers_count": 90000, "html_url": "https://github.com/b/two", "language": null}
  ]
}
"""

REMOTEOK = """
[
  {"legal": "terms of service notice, not a job"},
  {"position": "Security Engineer", "company": "GitLab", "url": "https://remoteok.com/x", "date": "2026-11-25T00:20:28+00:00"}
]
"""


def _spec(source: str) -> dict:
    data = yaml.safe_load(
        (ROOT / "config" / "extractors" / f"{source}.yaml").read_text(encoding="utf-8")
    )
    return data["versions"][0]


def test_factory_dispatches_on_mode():
    assert isinstance(build(_spec("books")), Extractor)
    assert isinstance(build(_spec("gh")), JsonExtractor)


def test_json_engine_reads_nested_container_and_typed_fields():
    records = build(_spec("gh")).extract(GITHUB, "https://api.github.com/")

    assert len(records) == 2
    assert records[0] == {
        "full_name": "a/one",
        "stars": 120000,
        "url": "https://github.com/a/one",
        "language": "Go",
    }
    assert records[1]["language"] is None
    schema = load_schema(ROOT / "schemas" / "gh.v1.json")
    assert all(v.ok for v in validate_many(records, schema))


def test_json_engine_drops_entries_missing_the_required_key():
    records = build(_spec("remoteok")).extract(REMOTEOK, "https://remoteok.com/")

    assert len(records) == 1
    assert records[0]["position"] == "Security Engineer"
    assert records[0]["company"] == "GitLab"


def test_json_engine_returns_nothing_for_non_json():
    assert build(_spec("gh")).extract("<html>not json</html>", "https://x/") == []


def test_html_engine_still_reads_hn_rows():
    markup = """
    <table><tr class="athing submission" id="1">
      <td><span class="rank">1.</span></td>
      <td class="title"><span class="titleline"><a href="https://example.test/post">A post</a></span></td>
    </tr></table>
    """
    records = build(_spec("hn")).extract(markup, "https://news.ycombinator.com/")

    assert records == [
        {"title": "A post", "url": "https://example.test/post", "rank": "1."}
    ]
