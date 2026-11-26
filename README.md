# Sentinel

A data pipeline that detects when a public source drifts, and proves any repair
against a fixed golden set before it is trusted.

Built from `SPEC.md` (v2, frozen — see the checksums below). `ACCEPTANCE.md` defines
what "done" means. `DEVIATIONS.md` records decisions the spec is silent on.

```
SPEC.md        5104140b6da994cf8c526e6678bd15ccbde6cd870afbadb8b70e15c822e359d2  (8159 bytes)
ACCEPTANCE.md  95ba7a6b1de4c3f0b3957178c0388fd736abdea1166dfa824282c93123588d24  (2088 bytes)
```

Live board: **https://sachin-singh-tanwar.github.io/sentinel/**

## What exists today

Build order is SPEC §13, and it is not skipped.

| Step | Scope | Status |
|---|---|---|
| 1 | `books` end-to-end, golden set, drift on injected breakage | **done** |
| 2 | gate + revert + tests for pass and fail paths | **done** |
| 3 | `/incidents/:id` payload with diff + golden report | **done** |
| 4 | dashboard: Board → Incident → Method, Pages deploy | **done** |
| 5 | remaining 4 sources (config only) | **configured + running**; golden sets awaited |
| 6 | staged-injection demo + badge | **done** |

43 tests pass. `books` is the only source with a frozen golden set, so it is the only
one where a repair can be certified; the other four are collected and validated but
are not repairable until their handover fixtures land.

## Run it

```bash
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python -m sentinel.cli run     --source books   # one real run
.venv\Scripts\python -m sentinel.cli run     --source hn      # any configured source
.venv\Scripts\python -m sentinel.cli state                   # per-source state
.venv\Scripts\python -m sentinel.cli inject  --source books   # staged demo breakage
.venv\Scripts\python -m sentinel.cli repair  --source books   # propose -> gate -> apply
.venv\Scripts\python -m sentinel.cli revert  --source books --to books.v1
.venv\Scripts\python -m sentinel.cli export  --out data      # static JSON for the dashboard
.venv\Scripts\python -m pytest -q
```

Exit codes: `0` ok, `2` refused or invalid config, `1` runtime failure.

`scripts/demo.py` runs the whole staged sequence (healthy → inject → drift → gate →
verified → revert) and writes the static JSON CI publishes.

## How it works

```
fetch ─┬─ snapshot (runs/<id>/snapshot.html)
       ├─ extract (versioned spec: books.v1, hn.v1, gh.v1, …)
       ├─ validate against schemas/<source>.v1.json
       ├─ drift signals (config/drift.yaml is the only source of thresholds)
       ├─ one state per source: DOWN > DRIFT > HEALTHY
       └─ incident opened on the HEALTHY → DRIFT transition
```

An extractor version is **data**, not code: a container selector plus per-field
selectors in `config/extractors/<source>.yaml`, then a row in the database. Repairing
a layout change is therefore a row change, and revert is one command.

Two engines, one dispatch point (`sentinel/factory.py`): `engine.py` parses HTML,
`json_engine.py` reads JSON. `mode: json` in the extractor spec selects the JSON
engine. Adding the four step-5 sources touched neither parser — it added four YAML
files, four schemas and four registry entries.

### The gate

```
field_accuracy >= 0.95  AND  no per-field regression  →  apply
otherwise                                             →  NEEDS_HUMAN, nothing applied
```

The heuristic (or a model) only proposes. The frozen golden set decides. A rejected
candidate is stored on the incident for review and is never made active.

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
| A1 | 5 sources, 0 with auth | 5 configured (`books`, `hn`, `gh`, `apify`, `remoteok`), 0 with auth | **pass** |
| A2 | 5 golden sets, 20 records each | `books` 20/20 sealed; `hn`/`gh`/`apify`/`remoteok` absent (handover awaited) | **UNVERIFIED** — 1 of 5 |
| A3 | HEALTHY → DRIFT in exactly 1 run | run 3 HEALTHY (20 rec) → inject → run 4 DRIFT (0 rec) | **pass** |
| A4 | Gate rejects a wrong repair | price+rating null → REJECT at 0.6000, nothing applied; truncated 10/20 → REJECT at 0.5000 | **pass** |
| A5 | Gate accepts a correct repair | PASS at 1.0000, `books.v2` created and made active | **pass** |
| A6 | Repairs are revertible | revert to `books.v1`, next run 20 rec, 0 schema failures, golden reproduced | **pass** |
| A7 | MTTR is real | `verified_at − drift_detected_at` = 4s, rendered in the UI | **pass** |
| A8 | Staged incidents labelled | `STAGED DEMO` badge rendered; 0 unlabelled staged incidents | **pass** |
| A9 | Refusals enforced | loader raises; CLI exits non-zero on `login: true` and `captcha: solve` | **pass** |
| A10 | Dashboard reads live API | 3 screens, 0 console errors in static and live-API modes; 50.49 kB gzip JS | **pass** |

## Layout

```
config/sources.yaml        source registry (refusal-checked on load)
config/drift.yaml          every drift threshold, one file
config/gate.yaml           field accuracy floor + zero-regression rule
config/extractors/*.yaml   versioned selectors, one file per source
schemas/*.v1.json          field types and required flags
fixtures/books/            sealed golden set + sha256
sentinel/                  config, fetch, engines, schema, drift, gate, repair, export, api, cli
scripts/                   one-time golden capture, staged demo
dashboard/                 React + Vite, three screens, static JSON or ?api=
tools/e2e/                 dev-only Playwright check (not a pipeline dependency)
.github/workflows/         test → collect → demo → data branch → build → Pages
```

Python 3.11, `httpx` + `lxml` + SQLite (WAL). No Playwright and no browser binaries in
the pipeline (SPEC §12 amendment); the browser check in `tools/e2e` is dev-only.
FastAPI is for local dev; the public demo is static and does not need a server.
