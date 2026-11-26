"""Candidate proposal — SPEC §6 step 2, heuristic first.

Reads the failing snapshot, finds the container and field hooks that actually exist in
it, and emits an extractor spec. It proposes; it never decides. The gate decides.

No LLM is required for v1: the heuristic handles a rename-style redesign, which is what
injection produces. A model, if added later, would emit the same spec shape.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from lxml import html as lxml_html

ENUM_VALUES = ["One", "Two", "Three", "Four", "Five"]


def _classes(element) -> list[str]:
    return (element.get("class") or "").split()


def _next_version(version: str) -> str:
    match = re.search(r"v(\d+)$", version)
    if not match:
        return f"{version}.v2"
    prefix = version[: match.start()]
    return f"{prefix}v{int(match.group(1)) + 1}"


def _container_signature(container: str) -> tuple[str | None, str | None]:
    match = re.search(r"//(\w+)\[contains\(@class,'([^']+)'\)\]", container)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _candidate_containers(tree) -> tuple[Counter, dict]:
    counts: Counter = Counter()
    samples: dict[tuple[str, str], Any] = {}

    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        for token in _classes(element):
            key = (element.tag, token)
            if element.xpath(".//a[@href]") or (element.tag == "a" and element.get("href")):
                counts[key] += 1
                samples.setdefault(key, element)

    return counts, samples


def _find_class_token(node, predicate) -> tuple[Any, str] | tuple[None, None]:
    for element in node.iter():
        if not isinstance(element.tag, str):
            continue
        for token in _classes(element):
            if predicate(token):
                return element, token
    return None, None


def _xpath_for(element, token: str) -> str:
    return f".//{element.tag}[contains(@class,'{token}')]"


def _depth(element) -> int:
    return sum(1 for _ in element.iterancestors())


def propose(
    snapshot: str,
    incumbent_spec: dict[str, Any],
    base_url: str,
) -> dict[str, Any] | None:
    """Derive a candidate spec from the failing snapshot. Returns None if it cannot."""
    tree = lxml_html.fromstring(snapshot)
    counts, samples = _candidate_containers(tree)
    if not counts:
        return None

    incumbent_tag, incumbent_token = _container_signature(incumbent_spec.get("container", ""))

    ranked = [
        (key, count)
        for key, count in counts.most_common()
        if count >= 3 and not (key[0] == incumbent_tag and key[1] == incumbent_token)
    ]
    # Deeper first: a grid wrapper and the card inside it both match every anchor, and
    # only the card carries the price and rating we need.
    ranked.sort(key=lambda item: (-item[1], -_depth(samples[item[0]])))

    for (tag, token), _count in ranked:
        fields = _derive_fields(samples[(tag, token)])
        if fields is None:
            continue
        return {
            "version": _next_version(incumbent_spec["version"]),
            "container": f"//{tag}[contains(@class,'{token}')]",
            "fields": fields,
            "proposed_by": "heuristic",
            "notes": f"derived from snapshot: container {tag}.{token}",
        }

    return None


def _derive_fields(sample) -> dict[str, Any] | None:
    fields: dict[str, Any] = {}

    anchor = sample.xpath(".//a[@title]")
    if anchor:
        fields["title"] = {"xpath": ".//a[@title]", "attr": "title"}
        fields["url"] = {"xpath": ".//a[@title]", "attr": "href", "absolute": True}
    else:
        anchors = sample.xpath(".//a[@href]")
        if anchors:
            fields["title"] = {"xpath": ".//a[@href]"}
            fields["url"] = {"xpath": ".//a[@href]", "attr": "href", "absolute": True}

    price_el, price_token = _find_class_token(sample, lambda t: "price" in t.lower())
    if price_el is not None:
        fields["price"] = {"xpath": _xpath_for(price_el, price_token), "parse": "money"}

    rating_el, _ = _find_class_token(sample, lambda t: t in ENUM_VALUES)
    if rating_el is not None:
        fields["rating"] = {
            "xpath": _xpath_for(rating_el, _classes(rating_el)[0]),
            "enum_from_class": ENUM_VALUES,
        }

    stock_el, stock_token = _find_class_token(
        sample, lambda t: "stock" in t.lower() or "avail" in t.lower()
    )
    if stock_el is not None:
        fields["stock"] = {"xpath": _xpath_for(stock_el, stock_token), "parse": "stock_count"}

    if not {"title", "price", "url", "rating"}.issubset(fields):
        return None
    return fields
