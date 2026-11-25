# Sentinel

A data pipeline that detects when a public source drifts, and proves any repair
against a fixed golden set before it is trusted.

Built from `SPEC.md` (v2, frozen — see the checksums below). `ACCEPTANCE.md` defines
what "done" means. `DEVIATIONS.md` records decisions the spec is silent on.

```
SPEC.md        5104140b6da994cf8c526e6678bd15ccbde6cd870afbadb8b70e15c822e359d2  (8159 bytes)
ACCEPTANCE.md  95ba7a6b1de4c3f0b3957178c0388fd736abdea1166dfa824282c93123588d24  (2088 bytes)
```

## What exists today

Build order is SPEC §13, and it is not skipped.

| Step | Scope | Status |
|---|---|---|
| 1 | `books` end-to-end, golden set, drift on injected breakage | code + drift **done**; golden set **awaited** |
| 2 | gate + revert + tests for pass and fail paths | not started |
| 3 | `/incidents/:id` payload with diff + golden report | not started |
| 4 | dashboard: Board → Incident → Method | not started |
| 5 | remaining 4 sources (config only) | not started |
| 6 | staged-injection demo + badge | not started |

## Run it

```bash
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python -m sentinel.cli run     --source books   # one real run
.venv\Scripts\python -m sentinel.cli state                   # per-source state
.venv\Scripts\python -m sentinel.cli inject  --source books   # staged demo breakage
.venv\Scripts\python -m sentinel.cli clear   --source books
.venv\Scripts\python -m pytest -q
```

Exit codes: `0` ok, `2` refused or invalid config, `1` runtime failure.

## How it works

```
fetch ──► snapshot (runs/<id>/snapshot.html)
      ──► extract (versioned: books.v1)
      ──► validate against schemas/books.v1.json
      ──► drift signals (config/drift.yaml is the only source of thresholds)
      ──► one state per source: DOWN > DRIFT > HEALTHY
      ──► incident opened on the HEALTHY → DRIFT transition
```

The state machine, gate, and MTTR are SPEC §6–§7. The gate is not built yet, so
nothing can currently mark an incident `VERIFIED`.

## Two rules that are enforced in code, not documented

- **Refusals.** A source entry with `auth:`, `login: true`, `captcha: solve`,
  `proxy_rotation: true`, `cookies:` or a token makes the loader exit non-zero with a
  clear message. See `sentinel/config.py::check_refusals`.
- **The golden set is frozen.** `sentinel/golden.py` has no write path for records.
  Every run is wrapped in `golden.guard()`, which fails if the file's bytes or mtime
  change while the system is running.

## ACCEPTANCE status

| # | Check | Observed | Verdict |
|---|---|---|---|
| A1 | 5 sources, 0 with auth | 1 configured (`books`), 0 with auth | **partial** — step 5 |
| A2 | 5 golden sets, 20 records each | `fixtures/books/golden.json` absent | **UNVERIFIED** — handover awaited |
| A3 | HEALTHY → DRIFT in exactly 1 run | run 3 HEALTHY (20 rec) → inject → run 4 DRIFT (0 rec) | **pass** |
| A4 | Gate rejects a wrong repair | gate not built | **not started** — step 2 |
| A5 | Gate accepts a correct repair | gate not built | **not started** — step 2 |
| A6 | Repairs are revertible | revert not built | **not started** — step 2 |
| A7 | MTTR is real | no incident can be resolved yet | **not started** — step 2 |
| A8 | Staged incidents labelled | `staged=1` in DB and API payload | **partial** — UI badge is step 4 |
| A9 | Refusals enforced | 6 loader tests + 2 CLI exit-code tests green | **pass** |
| A10 | Dashboard reads live API | no dashboard | **not started** — step 4 |

## Layout

```
config/sources.yaml    source registry (refusal-checked on load)
config/drift.yaml      every drift threshold, one file
schemas/books.v1.json  field types, required flags
fixtures/books/        golden set (awaiting handover) — see its README
sentinel/              config, fetch, extractors, schema, drift, pipeline, api, cli
tests/                 22 tests
```

Python 3.11, `httpx` + `lxml` + SQLite (WAL). No Playwright, no browser binaries
(SPEC §12 amendment). FastAPI is for local dev only; the public demo will be static
(SPEC §14).
