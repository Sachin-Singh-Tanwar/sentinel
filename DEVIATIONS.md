# DEVIATIONS

`SPEC.md` was amended once, under the owner-locked A2 decision recorded in §3 and
item 7 below; otherwise it is frozen. This file records (a) any deviation and
(b) decisions the spec is silent on, so they are reviewable rather than buried.

**Status: two authorised reconciliation decisions, both made on 2026-11-26
(items 1 and 7).** Everything else follows SPEC §13 order.

## Deviations

### 1. `books.v1` schema reconciliation (authorised)

Three versions of the books metadata existed before A2: SPEC §3 marked both
`rating` and `stock` required; the independent capture script listed both as
optional; the report showed `rating` present and `stock: null`. The catalogue
listing does not publish stock counts at all — it renders `In stock`, while the
count (`In stock (22 available)`) exists only on each book's detail page. The
first capture therefore recorded `stock: 0` for all 20 records, which is wrong for
the real source and would have taught a correct extractor to be wrong.

**Owner-locked decision:** `books.v1` required fields are `title`, `price`,
`rating`, `url`; `stock` is **OPTIONAL**. This supersedes both earlier variants.
`SPEC.md` §3 and `schemas/books.v1.json` now say exactly that, so there is no
second silent schema.

Consequence: a run is **one** request (the listing page), not 21. `stock` is still
extracted when a page publishes it; it is simply not allowed to decide whether a
repair is correct. The sealed golden set keeps 20 records of `title, price,
rating, url` with `stock: null` and is untouched at
`ee01e30e0b65063abc6f79c0c2c92829fbec9e18b9d2eb84c1ec94b4e82d197d`.

## Spec-silent decisions (implementation notes, not deviations)

### 2. `drift_score` is named but never defined

SPEC §5/§9 require a drift score per source; no formula is given. Defined here as the
worst continuous severity in `[0,1]`:

```
max(schema_fail_rate, required_null_rate, 1 - record_count_ratio)
```

Discrete streaks (`empty_streak`, `http_fail_streak`) do not move the score; they move
the state. If the spec later defines a score, this is the one line to replace.

### 3. Drift injection cannot mutate a public site

SPEC §8 wants `POST /admin/inject-drift` to "break one source deliberately".
books.toscrape.com cannot be changed by us. Injection therefore applies a
deterministic rewrite of the class hooks the extractor depends on
(`product_pod` → `product_card`, `star-rating` → `rating-stars`,
`price_color` → `price-value`, `instock availability` → `stock-badge`), served through
the same fetch → extract → validate path as a real response. The observable effect is
identical to an upstream redesign: `books.v1` extracts 0 records and drift fires on
the next run.

Every incident opened while an injection is active is written with `staged = 1`.

### 4. `http_status` sentinel values

`NULL` = no request was attempted (an offline/test run with a supplied document).
`0` = transport failure. Non-2xx = an HTTP response that failed. `http_fail_streak`
counts the latter two and ignores `NULL`, so offline test runs cannot manufacture a
DOWN state.

### 5. Run history lives on the `data` branch

SPEC §14 says the public demo reads static JSON from a `data` branch and that the
branch is append-only. GitHub runners are ephemeral, so the SQLite database that holds
run history, incidents and MTTR is committed to that same branch and restored at the
start of the next run. Each CI run clones the branch, adds exactly one commit, and
pushes it — history is appended, never rewritten. The dashboard still reads only the
JSON, so it keeps working when the API is down.

### 6. The four step-5 golden sets have landed

Resolved on 2026-11-26: the partner-verified `hn`, `gh`, `apify` and `remoteok`
fixtures were copied unchanged from the VM and sealed. They were not re-captured by
the running system (SPEC §4). ACCEPTANCE A2 is now reported as **5/5**; A1, A3–A10
are unaffected.

### 7. Step-5 schemas reconciled with partner metadata (authorised)

The four handover fixtures carry `schema_version`, `required_fields` and
`optional_fields`. Their field names did not match the first local drafts
(`hn.rank` was a required string; `gh` used `full_name`/`url`; `apify` used
`username`/`url`/`users`; `remoteok` required `url`). Those drafts are replaced,
not kept as a second mapping:

| schema | required | optional |
|---|---|---|
| `hn.v1` | `title`, `url` | `rank`, `points` |
| `gh.v1` | `repo`, `stars` | `language`, `pushed_at` |
| `apify.v1` | `title`, `owner` | `total_users`, `pricing_model` |
| `remoteok.v1` | `position`, `company` | `tags`, `date` |

`SPEC.md` §3, `schemas/*.v1.json` and `config/extractors/*.yaml` now use this one
field set per source. `tags` is a `list`; `schema.py` validates that type and
`json_engine.py` passes lists through unchanged. `gh` keeps its five null
`language` values because `language` is optional. All four fixtures have zero nulls
in their required fields.
