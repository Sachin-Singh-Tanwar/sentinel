# Sentinel — ACCEPTANCE

Every check must be machine-verifiable and reported with its observed value.
A check that cannot be observed is reported as `UNVERIFIED` with the reason — never as a pass.

| # | Check | How it is verified | Pass condition |
|---|---|---|---|
| A1 | Five sources configured, none require auth | `config/sources.yaml` parsed; every entry has no `auth:` block | 5 sources, 0 with auth |
| A2 | Golden sets exist and load | `fixtures/<source>/golden.json` parsed for all 5 | 5 files, 20 records each |
| A3 | Drift is detected, not assumed | inject drift on `books`, run once | state HEALTHY → DRIFT in exactly 1 run |
| A4 | Gate rejects a wrong repair | unit test with a deliberately broken candidate extractor | gate = REJECT, accuracy < 0.95, nothing applied |
| A5 | Gate accepts a correct repair | unit test with a known-good candidate | gate = PASS, version id created |
| A6 | Repairs are revertible | apply A5 candidate, then revert | previous extractor restored, run reproduces golden set |
| A7 | MTTR is real | resolve one incident | `verified_at - drift_detected_at` present, > 0, shown in UI |
| A8 | Staged incidents are labelled | inject drift, open incident in UI | `STAGED DEMO` badge rendered; unlabelled staged incidents = 0 |
| A9 | Refusals are enforced, not documented | config with `login: true` or `captcha: solve` | loader exits non-zero with a clear error |
| A10 | Dashboard reads live API | load dashboard pointing at running API | 3 screens render, 0 console errors, bundle < 250 KB gzip |

## Anti-gaming rules

- Golden sets are committed files; the running system must not rewrite them (assert file mtime unchanged after a repair).
- Drift thresholds are constants read from one config file, not scattered literals.
- A demo incident is never presented as a real outage. If `staged = true`, the word **staged** appears in the UI and in the API payload.

## Out of scope for acceptance

- Visual polish beyond the three screens
- Performance beyond "dashboard loads in under 2s on a warm API"
- Any claim about production scale
