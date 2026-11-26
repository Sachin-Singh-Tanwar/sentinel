"""One-time golden-set capture. Authoring tool, not part of the running system.

Deliberately independent of `sentinel/engine.py`: it parses the raw markup with regex
and does not import the extractor. If both agree on all 20 records, the fixture is not
just the extractor's own opinion of itself. The result is then sealed by sha256 and
never rewritten (sentinel/golden.py has no write path).

Usage:
    python scripts/capture_golden.py            # from the saved fixture
    python scripts/capture_golden.py --live     # from the live listing page
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "fixtures" / "books" / "golden.json"
FIXTURE = ROOT / "tests" / "fixtures" / "books_listing.html"
BASE = "https://books.toscrape.com/catalogue/page-1.html"

BLOCK = re.compile(r'<article class="product_pod">(.*?)</article>', re.S)
TITLE = re.compile(r'<h3><a href="([^"]+)" title="([^"]*)"')
PRICE = re.compile(r'<p class="price_color">\s*[^\d]*([\d.]+)')
RATING = re.compile(r'<p class="star-rating (One|Two|Three|Four|Five)"')


def capture(markup: str) -> list[dict]:
    records = []
    for block in BLOCK.findall(markup):
        title_match = TITLE.search(block)
        price_match = PRICE.search(block)
        rating_match = RATING.search(block)
        if not (title_match and price_match and rating_match):
            raise SystemExit("capture: a product block is missing title/price/rating")

        href, title = title_match.groups()
        records.append(
            {
                "title": html.unescape(title).strip(),
                "price": float(price_match.group(1)),
                "rating": rating_match.group(1),
                "url": urljoin(BASE, href),
                "stock": None,  # the listing page does not publish stock counts
            }
        )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="fetch the live listing page")
    args = parser.parse_args(argv)

    if TARGET.exists():
        print(
            f"refusing: {TARGET} already exists. The golden set is captured once and "
            "never regenerated (SPEC §4).",
            file=sys.stderr,
        )
        return 1

    if args.live:
        import httpx

        markup = httpx.get(BASE, timeout=30, follow_redirects=True).text
        origin = "live listing page"
    else:
        markup = FIXTURE.read_text(encoding="utf-8")
        origin = str(FIXTURE.relative_to(ROOT))

    records = capture(markup)
    if len(records) != 20:
        print(f"refusing: captured {len(records)} records, SPEC §4 requires 20", file=sys.stderr)
        return 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "books",
        "schema": "books.v1",
        "captured_from": origin,
        "note": "stock is null: the listing page does not publish stock counts",
        "records": records,
    }
    TARGET.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(f"captured {len(records)} records from {origin}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
