"""The extraction engine.

One generic engine, versioned by data. An extractor version is a container XPath plus
per-field XPaths (config/extractors/<source>.yaml, then the DB once active). Adding a
version never adds a code path — that is what makes SPEC §13 step 5 config-only and
makes apply/revert a row change.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from lxml import html as lxml_html

MONEY_RE = re.compile(r"\d+(?:\.\d+)?")
STOCK_RE = re.compile(r"(\d+)\s+available", re.IGNORECASE)


def _node_text(node) -> str:
    return " ".join(part.strip() for part in node.itertext() if part.strip())


def _coerce(raw: str | None, spec: dict[str, Any]) -> Any:
    if raw is None:
        return None
    if spec.get("parse") == "money":
        match = MONEY_RE.search(raw)
        return float(match.group()) if match else None
    if spec.get("parse") == "stock_count":
        match = STOCK_RE.search(raw)
        return int(match.group(1)) if match else None
    return raw.strip() or None


def _field_value(node, spec: dict[str, Any], base_url: str) -> Any:
    xpath = spec.get("xpath")
    if not xpath:
        return None
    found = node.xpath(xpath)
    if not found:
        return None

    target = found[0]

    if "enum_from_class" in spec:
        classes = (target.get("class") or "").split()
        for token in classes:
            if token in spec["enum_from_class"]:
                return token
        return None

    if "attr" in spec:
        raw = target.get(spec["attr"])
        if raw and spec.get("absolute"):
            return urljoin(base_url, raw)
        return raw.strip() or None if raw else None

    return _coerce(_node_text(target), spec)


class Extractor:
    """A versioned extractor, fully described by its spec."""

    def __init__(self, spec: dict[str, Any]):
        if "version" not in spec or "container" not in spec or "fields" not in spec:
            raise ValueError("extractor spec needs 'version', 'container' and 'fields'")
        self.spec = spec

    @property
    def version(self) -> str:
        return self.spec["version"]

    @property
    def fields(self) -> list[str]:
        return list(self.spec["fields"])

    def extract(self, document: str, base_url: str) -> list[dict]:
        tree = lxml_html.fromstring(document)
        out: list[dict] = []

        for node in tree.xpath(self.spec["container"]):
            record = {}
            for name, field_spec in self.spec["fields"].items():
                record[name] = _field_value(node, field_spec, base_url)
            out.append(record)

        return out
