# Golden-set provenance

No `golden.json` bytes were changed to create this file. The four handover sets were
copied into the repo unchanged and verified with `golden.load()` +
`golden.verify_seal()`. `captured_at` below is read from each file; where the file has
no such field, the value is `UNKNOWN`.

| Source | Source URL used at capture | `captured_at` from file | sha256 | Method |
|---|---|---|---|---|
| `books` | `https://books.toscrape.com/catalogue/page-1.html` | `UNKNOWN` | `ee01e30e0b65063abc6f79c0c2c92829fbec9e18b9d2eb84c1ec94b4e82d197d` | VM-only `capture_golden.py`, Python stdlib `urllib.request` GET (UA `SentinelGoldenSet/1.0`, `ssl.create_default_context()`, timeout 30 s), UTF-8 decode with `replace`, `re` over `<article class="product_pod">` blocks (first 20), then `json.dump(..., indent=2, ensure_ascii=False)`. |
| `hn` | `https://news.ycombinator.com/` | `2026-11-25T16:38:19+00:00` | `a944344f187e1f3d3e09c920a69335b12756e711e4e480c7644601a68af19e82` | VM-only `capture_golden.py`, Python stdlib `urllib.request` GET (UA `SentinelGoldenSet/1.0`, `ssl.create_default_context()`, timeout 30 s), UTF-8 decode with `replace`, `re` for rank/titleline/score, first 20 titles with `rank = i + 1` and `points = 0` fallbacks, then `json.dump(..., indent=2, ensure_ascii=False)`. |
| `gh` | `https://api.github.com/search/repositories?q=stars:%3E10000&sort=stars&order=desc&per_page=20` | `2026-11-25T16:38:20+00:00` | `ed0a15b043eaad83475114fab4b5520127ad419da74123565e5b930e3811b717` | VM-only `capture_golden.py`, Python stdlib `urllib.request` GET (UA `SentinelGoldenSet/1.0`, `ssl.create_default_context()`, timeout 30 s), UTF-8 decode with `replace`, `json.loads`, first 20 `items` mapped to `repo`, `stars`, `language` (nullable), `pushed_at`, then `json.dump(..., indent=2, ensure_ascii=False)`. |
| `apify` | `https://api.apify.com/v2/store?limit=20` | `2026-11-25T16:38:22+00:00` | `15a3c2600bea1728ffa7e070fa53a77cc811782db2ab3041813cd4378eec2f56` | VM-only `capture_golden.py`, Python stdlib `urllib.request` GET (UA `SentinelGoldenSet/1.0`, `ssl.create_default_context()`, timeout 30 s), UTF-8 decode with `replace`, `json.loads(body)["data"]["items"][:20]`, mapped to `title`, `owner`, `total_users`, `pricing_model`, then `json.dump(..., indent=2, ensure_ascii=False)`. |
| `remoteok` | `https://remoteok.com/api` | `2026-11-25T16:38:24+00:00` | `2a8f3e99acbee213c7ac111aa256c11b6b79c9b542a318b47f6297301bccd30e` | VM-only `capture_golden.py`, Python stdlib `urllib.request` GET (UA `SentinelGoldenSet/1.0`, `ssl.create_default_context()`, timeout 30 s), UTF-8 decode with `replace`, `json.loads`, `d[1:][:20]` mapped to `position`, `company`, `tags[:6]`, `date`, then `json.dump(..., indent=2, ensure_ascii=False)`. |

The capture script lived only on the VM at
`/home/ubuntu/projects/sentinel/capture_golden.py`. It wrote each golden file with
`indent=2`, `ensure_ascii=False`, a UTC `captured_at` at second precision, `frozen:
true`, `count`, `required_fields` and `optional_fields`. It did **not** save the raw
HTTP payload. Because no raw payload was archived and live data has changed since
capture, the per-source `PASS 1.0000` re-extraction gate is `UNVERIFIED` for `hn`,
`gh`, `apify` and `remoteok`; comparing a golden file to itself is not proof.
