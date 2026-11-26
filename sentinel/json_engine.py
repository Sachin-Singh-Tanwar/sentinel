"""JSON extractor. A separate module on purpose: SPEC §13 step 5 is config-only, so the
HTML parser in engine.py is not modified to accommodate JSON sources.

A spec looks like:

    mode: json
    container: data.items        # dot path to the list ("" = the document is the list)
    require: position            # skip entries missing this key (e.g. legal notices)
    fields:
      position: {path: position}
      company:  {path: company}
      date:     {path: date}
"""

from __future__ import annotations

import json
from typing import Any


def _dig(node: Any, path: str) -> Any:
    if not path:
        return node
    current = node
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _coerce(raw: Any, spec: dict[str, Any]) -> Any:
    if raw is None:
        return None
    parse = spec.get("parse")
    try:
        if parse == "int":
            return int(raw)
        if parse == "float":
            return float(raw)
    except (TypeError, ValueError):
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, (int, float, bool, list)):
        return raw
    return None


class JsonExtractor:
    def __init__(self, spec: dict[str, Any]):
        if "version" not in spec or "fields" not in spec:
            raise ValueError("json extractor spec needs 'version' and 'fields'")
        self.spec = spec

    @property
    def version(self) -> str:
        return self.spec["version"]

    @property
    def fields(self) -> list[str]:
        return list(self.spec["fields"])

    def extract(self, document: str, base_url: str) -> list[dict]:
        try:
            payload = json.loads(document)
        except json.JSONDecodeError:
            return []

        items = _dig(payload, self.spec.get("container", ""))
        if not isinstance(items, list):
            return []

        required_key = self.spec.get("require")
        out: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if required_key and _dig(item, required_key) in (None, ""):
                continue

            record = {}
            for name, field_spec in self.spec["fields"].items():
                record[name] = _coerce(_dig(item, field_spec["path"]), field_spec)
            out.append(record)

        return out
