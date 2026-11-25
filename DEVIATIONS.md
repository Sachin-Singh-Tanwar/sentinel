# DEVIATIONS

`SPEC.md` is frozen and was not edited. This file records (a) any deviation and
(b) decisions the spec is silent on, so they are reviewable rather than buried.

**Status: no deviations.** The build follows SPEC §13 order. Nothing in the spec has
been contradicted.

## Spec-silent decisions (implementation notes, not deviations)

### 1. `stock` requires one detail request per book — forced by the source

SPEC §3 requires `stock` to be an integer. The catalogue listing only publishes
`In stock` with no count; the count (`In stock (22 available)`) exists only on each
book's detail page. `books.v1` therefore makes 21 requests per run (1 listing + 20
detail pages). This is a fact about the source, not a design choice.

Consequence: a run costs ~21 requests and takes a few seconds. If that becomes
unacceptable, the schema is what has to change, not the extractor's honesty.

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
