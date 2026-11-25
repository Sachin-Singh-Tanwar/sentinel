"""HTTP fetch + the deliberate layout mutation used by the staged demo.

SPEC §8: POST /admin/inject-drift breaks one source deliberately. Since
books.toscrape.com is a static playground we cannot make the real site change, so
injection rewrites the class hooks the extractor depends on — the same observable
effect as an upstream redesign, deterministic and reversible.
"""

from __future__ import annotations

import httpx

USER_AGENT = (
    "Sentinel/0.1 (public data demo; https://github.com/Sachin-Singh-Tanwar/sentinel)"
)

TIMEOUT = httpx.Timeout(20.0, connect=10.0)

# rev 2 simulates a redesign. Each rename is chosen so it does NOT accidentally
# satisfy a v1 selector (e.g. 'stock-badge' contains neither 'instock' nor
# 'availability').
LAYOUT_REV_2 = (
    ("product_pod", "product_card"),
    ("star-rating", "rating-stars"),
    ("price_color", "price-value"),
    ("instock availability", "stock-badge"),
    ("icon-ok", "icon-check"),
)


def mutate_layout(document: str, rev: int) -> str:
    """Apply the injected layout revision to raw markup."""
    if rev <= 1:
        return document
    if rev != 2:
        raise ValueError(f"unknown layout rev {rev}")

    out = document
    for old, new in LAYOUT_REV_2:
        out = out.replace(old, new)
    return out


def new_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def fetch_text(client: httpx.Client, url: str) -> tuple[int, str]:
    response = client.get(url)
    return response.status_code, response.text
