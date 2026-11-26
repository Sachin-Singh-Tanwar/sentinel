# DEVIATIONS

`SPEC.md` is frozen and was not edited. This file records (a) any deviation and
(b) decisions the spec is silent on, so they are reviewable rather than buried.

**Status: one deviation, authorised by the owner on 2026-11-26 (item 1).**
Everything else follows SPEC §13 order.

## Deviations

### 1. `stock` is no longer a required field (authorised)

SPEC §3's example schema marks `stock` as `required: true`. The catalogue listing
does not publish stock counts at all — it renders `In stock`, while the count
(`In stock (22 available)`) exists only on each book's detail page. The owner's
first capture therefore recorded `stock: 0` for all 20 records, which is wrong for
the real source and would have taught a correct extractor to be wrong.

Decision: `books.v1` required fields are `title`, `price`, `url`. `rating` and
`stock` are optional, and golden records carry `stock: null`.

Consequence: a run is **one** request (the listing page), not 21. `stock` is still
extracted when a page publishes it; it is simply not allowed to decide whether a
repair is correct. The golden set keeps 20 records of `title, price, rating, url`
with `stock: null` and stays sealed at
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

### 6. The four step-5 sources have no golden set yet

`hn`, `gh`, `apify` and `remoteok` are configured, run, and validated against their
schemas, but their 20-record golden sets were to be handed over from the VM and are
not in this repo. They are never self-captured, because a golden set the system
produced cannot certify the system (SPEC §4). ACCEPTANCE A2 is reported as
**UNVERIFIED** for those four until the handover files land; A1, A3–A10 are unaffected.
