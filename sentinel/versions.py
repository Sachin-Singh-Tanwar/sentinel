"""Extractor version seeding and lookup."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import db as store
from .config import Source

ROOT = Path(__file__).resolve().parent.parent


class SpecConflict(RuntimeError):
    """A configured spec changed without a new version id."""


def _canonical(spec: dict) -> dict:
    return json.loads(json.dumps(spec, sort_keys=True))


def config_versions(source: Source) -> list[dict]:
    path = ROOT / "config" / "extractors" / f"{source.id}.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("versions", [])


def ensure_active(conn, source: Source) -> dict:
    """Reconcile configured specs with stored versions, then return the active spec.

    A stored spec and a YAML spec with the same (source, version) must be identical.
    Changing fields is a migration: it needs a new version id. A configured version
    that is not stored yet is inserted as a candidate and activated; the previous
    active row is retired. A version created by a gated repair and absent from YAML
    is left alone, because it is runtime data rather than a config rewrite.
    """
    configured = config_versions(source)
    if not configured:
        raise RuntimeError(f"no extractor config available for '{source.id}'")

    by_version = {spec["version"]: _canonical(spec) for spec in configured}
    target = source.extractor
    if target not in by_version:
        raise RuntimeError(
            f"source '{source.id}' names extractor '{target}', which is absent from config"
        )

    for stored_row in store.versions(conn, source.id):
        version = stored_row["version"]
        if version in by_version and _canonical(json.loads(stored_row["spec"])) != by_version[version]:
            raise SpecConflict(
                f"extractor spec changed for same version '{version}' on source '{source.id}'; "
                "bump the version id instead of rewriting a stored spec"
            )

    row = store.active_version(conn, source.id)
    if row is None:
        for spec in configured:
            store.add_version(
                conn,
                source.id,
                spec,
                status="active" if spec["version"] == target else "candidate",
                notes=spec.get("notes"),
            )
    elif store.get_version(conn, source.id, target) is None:
        spec = next(spec for spec in configured if spec["version"] == target)
        store.add_version(conn, source.id, spec, status="candidate", notes=spec.get("notes"))
        store.set_active(conn, source.id, target)
    elif row["version"] in by_version and row["version"] != target:
        store.set_active(conn, source.id, target)

    row = store.active_version(conn, source.id)
    if row is None:
        raise RuntimeError(f"no extractor version available for '{source.id}'")

    spec = json.loads(row["spec"])
    spec.setdefault("version", row["version"])
    return spec
