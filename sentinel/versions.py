"""Extractor version seeding and lookup."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import db as store
from .config import Source

ROOT = Path(__file__).resolve().parent.parent


def config_versions(source: Source) -> list[dict]:
    path = ROOT / "config" / "extractors" / f"{source.id}.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("versions", [])


def ensure_active(conn, source: Source) -> dict:
    """Return the active extractor spec, seeding from config on first use."""
    row = store.active_version(conn, source.id)
    if row is None:
        seeded = config_versions(source)
        for index, spec in enumerate(seeded):
            store.add_version(
                conn,
                source.id,
                spec,
                status="active" if index == 0 else "candidate",
                notes=spec.get("notes"),
            )
        row = store.active_version(conn, source.id)

    if row is None:
        raise RuntimeError(f"no extractor version available for '{source.id}'")

    spec = json.loads(row["spec"])
    spec.setdefault("version", row["version"])
    return spec
