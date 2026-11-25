"""The golden set — SPEC §4.

The golden set is the only thing allowed to certify a repair. It is captured once,
committed, and frozen. Nothing in this module can write golden records: there is no
write path on purpose, so a broken extractor can never certify itself.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .config import Source
from .schema import load_schema, validate_record

# SPEC §4: 20 archived records per source.
GOLDEN_SIZE = 20


class GoldenMissing(RuntimeError):
    """The handover file is not in the repo yet."""


class GoldenInvalid(RuntimeError):
    """The handover file is present but is not a usable golden set."""


class GoldenMutated(RuntimeError):
    """The golden file changed while the system was running."""


@dataclass(frozen=True)
class GoldenSet:
    source: str
    path: Path
    records: list[dict]
    sha256: str
    mtime_ns: int

    def __len__(self) -> int:
        return len(self.records)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(source: Source) -> GoldenSet:
    path = source.golden_path
    if not path.exists():
        raise GoldenMissing(
            f"golden set for '{source.id}' is missing at {path}. "
            "Golden sets are handed over as fixtures and must not be captured by the "
            "running system (SPEC §4). Refusing to continue."
        )

    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    stat = path.stat()

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GoldenInvalid(f"{path} is not valid JSON: {exc}") from exc

    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise GoldenInvalid(f"{path} has no 'records' list")

    if len(records) != GOLDEN_SIZE:
        raise GoldenInvalid(
            f"{path} holds {len(records)} records, SPEC §4 requires exactly {GOLDEN_SIZE}"
        )

    schema = load_schema(source.schema_path)
    for index, record in enumerate(records):
        validation = validate_record(record, schema)
        if not validation.ok:
            problems = ", ".join(f"{e.field}: {e.reason}" for e in validation.errors)
            raise GoldenInvalid(f"{path} record {index} fails {schema['id']}: {problems}")

    return GoldenSet(
        source=source.id,
        path=path,
        records=records,
        sha256=digest,
        mtime_ns=stat.st_mtime_ns,
    )


def fingerprint_file(source: Source) -> Path:
    return source.golden_path.parent / "golden.sha256"


def seal(source: Source, golden: GoldenSet) -> Path:
    """Record the handover checksum once. Refuses to overwrite an existing seal."""
    target = fingerprint_file(source)
    if target.exists():
        raise GoldenMutated(
            f"{target} already exists; a seal is written once at handover and never updated"
        )
    target.write_text(f"{golden.sha256}  {source.golden_path.name}\n", encoding="utf-8")
    return target


def verify_seal(source: Source, golden: GoldenSet) -> None:
    target = fingerprint_file(source)
    if not target.exists():
        return
    expected = target.read_text(encoding="utf-8").split()[0].strip()
    if expected != golden.sha256:
        raise GoldenMutated(
            f"{source.golden_path} does not match its handover seal "
            f"(expected {expected[:12]}…, found {golden.sha256[:12]}…)"
        )


@contextmanager
def guard(source: Source):
    """Assert the golden file is byte- and mtime-identical before and after work."""
    path = source.golden_path
    if not path.exists():
        yield None
        return

    before_sha = sha256_of(path)
    before_mtime = path.stat().st_mtime_ns
    try:
        yield before_sha
    finally:
        after_sha = sha256_of(path)
        after_mtime = path.stat().st_mtime_ns
        if after_sha != before_sha or after_mtime != before_mtime:
            raise GoldenMutated(
                f"{path} changed during the run "
                f"(sha {before_sha[:12]}… -> {after_sha[:12]}…, mtime {before_mtime} -> {after_mtime})"
            )
