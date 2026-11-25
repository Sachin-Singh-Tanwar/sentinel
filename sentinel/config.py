"""Config loading + refusal enforcement.

SPEC §1/§11: Sentinel never authenticates, never solves CAPTCHAs, never rotates
proxies. ACCEPTANCE A9 requires that this is enforced by the loader with a
non-zero exit, not merely documented.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import yaml

ROOT = Path(__file__).resolve().parent.parent

SOURCES_PATH = Path(os.environ.get("SENTINEL_SOURCES", ROOT / "config" / "sources.yaml"))
DRIFT_PATH = Path(os.environ.get("SENTINEL_DRIFT", ROOT / "config" / "drift.yaml"))


class RefusalError(RuntimeError):
    """Raised when a config asks for something Sentinel refuses to do."""


class ConfigError(RuntimeError):
    """Raised when a config is malformed."""


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    access: str
    url: str
    schema_path: Path
    golden_path: Path
    extractor: str
    drift_character: str = ""


def _refuse(source_id: str, detail: str) -> NoReturn:
    raise RefusalError(
        f"refused: source '{source_id}' {detail}. "
        "Sentinel does not authenticate, solve CAPTCHAs, or rotate proxies "
        "(SPEC §1, §11). Remove the directive from config/sources.yaml."
    )


def check_refusals(entry: dict[str, Any]) -> None:
    """Refuse any source entry that requires defeating a protection mechanism."""
    sid = str(entry.get("id", "<unnamed>"))

    if entry.get("auth") not in (None, {}, False, ""):
        _refuse(sid, "declares an 'auth' block")

    if entry.get("login") is True:
        _refuse(sid, "sets 'login: true'")

    captcha = entry.get("captcha")
    if captcha not in (None, False, "none", "no", "off"):
        _refuse(sid, f"sets 'captcha: {captcha}'")

    if entry.get("proxy") or entry.get("proxy_rotation") is True:
        _refuse(sid, "requests proxy rotation")

    for key in ("cookies", "session", "credentials", "token"):
        if entry.get(key):
            _refuse(sid, f"supplies '{key}'")


def load_sources(path: Path | str | None = None) -> list[Source]:
    path = Path(path) if path else SOURCES_PATH
    if not path.exists():
        raise ConfigError(f"missing source registry: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ConfigError(f"{path} has no 'sources' list")

    sources: list[Source] = []
    seen: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"{path}: every source must be a mapping")

        check_refusals(entry)

        sid = entry.get("id")
        if not sid:
            raise ConfigError(f"{path}: source without an 'id'")
        if sid in seen:
            raise ConfigError(f"{path}: duplicate source id '{sid}'")
        seen.add(sid)

        for key in ("url", "schema", "golden", "extractor"):
            if not entry.get(key):
                raise ConfigError(f"{path}: source '{sid}' is missing '{key}'")

        sources.append(
            Source(
                id=sid,
                name=entry.get("name", sid),
                access=entry.get("access", "html"),
                url=entry["url"],
                schema_path=ROOT / entry["schema"],
                golden_path=ROOT / entry["golden"],
                extractor=entry["extractor"],
                drift_character=entry.get("drift_character", ""),
            )
        )

    return sources


def load_thresholds(path: Path | str | None = None) -> dict[str, Any]:
    """Load drift thresholds. The only place threshold values may come from."""
    path = Path(path) if path else DRIFT_PATH
    if not path.exists():
        raise ConfigError(f"missing drift config: {path}")

    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("window", "signals", "state_precedence"):
        if key not in cfg:
            raise ConfigError(f"{path}: missing '{key}'")

    return cfg


def get_source(source_id: str, path: Path | str | None = None) -> Source:
    for src in load_sources(path):
        if src.id == source_id:
            return src
    raise ConfigError(f"unknown source '{source_id}'")
