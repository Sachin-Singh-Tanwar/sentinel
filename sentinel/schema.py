"""Schema loading and per-record validation — SPEC §3.

A record that fails type or enum validation counts as a schema failure,
not an empty row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FieldError:
    field: str
    reason: str


@dataclass
class Validation:
    errors: list[FieldError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def required_null_fields(self) -> list[str]:
        return [e.field for e in self.errors if e.reason == "required field is null"]


def load_schema(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "id" not in data or "fields" not in data:
        raise ValueError(f"{path}: schema needs 'id' and 'fields'")
    return data


def _check_type(spec: dict[str, Any], value: Any) -> str | None:
    kind = spec.get("type")
    if kind == "string":
        return None if isinstance(value, str) and value.strip() else "not a non-empty string"
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "not a number"
        return None
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return "not an integer"
        return None
    if kind == "enum":
        allowed = spec.get("values", [])
        return None if value in allowed else f"not one of {allowed}"
    if kind == "url":
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return "not an http(s) url"
        return None
    return f"unknown schema type '{kind}'"


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> Validation:
    out = Validation()
    for name, spec in schema["fields"].items():
        value = record.get(name)
        required = bool(spec.get("required"))

        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                out.errors.append(FieldError(name, "required field is null"))
            continue

        reason = _check_type(spec, value)
        if reason:
            out.errors.append(FieldError(name, reason))

    return out


def validate_many(records: list[dict[str, Any]], schema: dict[str, Any]) -> list[Validation]:
    return [validate_record(r, schema) for r in records]
