"""Picks the extractor implementation for a spec.

Adding a source is a config change: `mode` decides whether the HTML engine or the JSON
engine reads it, and neither engine knows any source by name.
"""

from __future__ import annotations

from typing import Any

from .engine import Extractor
from .json_engine import JsonExtractor


def build(spec: dict[str, Any]):
    if spec.get("mode") == "json":
        return JsonExtractor(spec)
    return Extractor(spec)
