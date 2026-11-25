# `fixtures/books/`

This directory holds the **frozen golden set** for `books` (SPEC §4): 20 archived
records, captured once, committed, never regenerated.

`golden.json` is **not in this repo yet.** It is handed over as a fixture from the VM
that captured it. Sentinel does not capture its own golden set — a pipeline that can
create the thing that certifies it can certify itself (SPEC §4, ACCEPTANCE
anti-gaming rules).

## What the handover must contain

`golden.json`:

```json
{ "records": [ /* exactly 20 records */ ] }
```

Each record must satisfy `schemas/books.v1.json`:

| field | type | notes |
|---|---|---|
| `title` | string | non-empty |
| `price` | number | e.g. `51.77` |
| `rating` | enum | `One`…`Five` |
| `stock` | integer | available count, from the detail page |
| `url` | url | absolute `https://books.toscrape.com/...` |

## What happens on handover

```bash
sentinel golden --source books     # validates 20 records against the schema
```

Then, once, the checksum is sealed:

```python
from sentinel import golden
golden.seal(source, golden.load(source))   # writes golden.sha256, refuses to overwrite
```

From then on every run is wrapped in `golden.guard(...)`, which fails loudly if the
file's bytes *or* mtime change while the system is running.

Until `golden.json` exists, `golden.load()` raises `GoldenMissing` and ACCEPTANCE **A2
is UNVERIFIED**. Nothing else silently substitutes for it.
