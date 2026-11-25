"""books.toscrape.com extractor, version books.v1 — SPEC §3.

Layout rev 1 = the site as it is today.

Data note: the catalogue listing only carries "In stock" with no count, while the
schema requires an integer `stock`. The count ("In stock (22 available)") exists only
on each book's detail page, so v1 enriches each record with one detail request.
That is a fact about the source, not a design choice.
"""

from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urljoin

from lxml import html as lxml_html

PRICE_RE = re.compile(r"\d+(?:\.\d+)?")
STOCK_RE = re.compile(r"(\d+)\s+available", re.IGNORECASE)

RATINGS = {"One", "Two", "Three", "Four", "Five"}


class BooksV1:
    version = "books.v1"
    layout_rev = 1

    # --- pure parsers (no network; used directly by tests) ------------------

    def parse_listing(self, document: str, base_url: str) -> list[dict]:
        tree = lxml_html.fromstring(document)
        out: list[dict] = []

        for pod in tree.xpath("//article[contains(@class,'product_pod')]"):
            link = pod.xpath(".//h3/a")
            if not link:
                continue
            anchor = link[0]
            title = (anchor.get("title") or anchor.text_content() or "").strip()
            href = anchor.get("href") or ""

            price_el = pod.xpath(".//p[contains(@class,'price_color')]/text()")
            price_text = price_el[0] if price_el else ""
            price_match = PRICE_RE.search(price_text or "")
            price = float(price_match.group()) if price_match else None

            rating = None
            for cls in (pod.xpath(".//p[contains(@class,'star-rating')]") or [None]):
                if cls is None:
                    break
                for token in (cls.get("class") or "").split():
                    if token in RATINGS:
                        rating = token

            availability = " ".join(
                t.strip() for t in pod.xpath(".//p[contains(@class,'availability')]//text()")
            ).strip()

            out.append(
                {
                    "title": title,
                    "price": price,
                    "rating": rating,
                    "stock": None,  # filled from the detail page
                    "url": urljoin(base_url, href),
                    "_availability": availability,
                }
            )

        return out

    def parse_detail(self, document: str) -> int | None:
        tree = lxml_html.fromstring(document)
        text = " ".join(
            t.strip()
            for t in tree.xpath(
                "//p[contains(@class,'availability')]//text() | "
                "//p[contains(@class,'instock')]//text()"
            )
        ).strip()
        match = STOCK_RE.search(text)
        if match:
            return int(match.group(1))
        if "in stock" in text.lower():
            return 1  # in stock, count not published
        return None

    # --- orchestration ------------------------------------------------------

    def extract(
        self,
        listing_html: str,
        base_url: str,
        detail_fetcher: Callable[[str], str | None] | None = None,
    ) -> list[dict]:
        records = self.parse_listing(listing_html, base_url)

        for record in records:
            if detail_fetcher is not None and record["stock"] is None:
                detail = detail_fetcher(record["url"])
                if detail:
                    record["stock"] = self.parse_detail(detail)

            record.pop("_availability", None)

        return records
