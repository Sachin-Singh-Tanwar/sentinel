"""Versioned extractors. An extractor version is a pure parser plus a layout rev.

Version ids are what the gate certifies and what revert restores (SPEC §6).
"""

from __future__ import annotations

from .books import BooksV1

REGISTRY: dict[str, object] = {
    BooksV1.version: BooksV1(),
}


def get_extractor(version: str):
    try:
        return REGISTRY[version]
    except KeyError:
        raise KeyError(f"unknown extractor version '{version}'") from None


__all__ = ["REGISTRY", "get_extractor", "BooksV1"]
