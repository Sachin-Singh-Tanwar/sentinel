"""The staged demo, end to end — SPEC §13 step 6.

healthy run -> inject drift -> one run -> DRIFT -> propose -> gate -> VERIFIED
-> clean run -> clear injection -> revert -> healthy again.

Every incident opened here is written with staged=1, which is what the UI badge reads.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sentinel import db as store  # noqa: E402
from sentinel import golden  # noqa: E402
from sentinel.config import get_source  # noqa: E402
from sentinel.export import export_all  # noqa: E402
from sentinel.pipeline import (  # noqa: E402
    clear_injection,
    healthy_snapshot_path,
    inject_drift,
    run_source,
)
from sentinel.repair import attempt_repair, revert  # noqa: E402


def main(out_dir: str = "data") -> int:
    conn = store.connect()
    source = get_source("books")

    # Start from a known-good baseline.
    clear_injection(conn, source.id)
    if store.get_version(conn, source.id, "books.v1"):
        revert(source, conn, "books.v1")

    baseline = run_source(source, conn)
    print(f"1. baseline        state={baseline['state']} records={baseline['records']} "
          f"extractor={baseline['extractor']}")

    inject_drift(conn, source.id)
    print("2. inject-drift    layout rev 2 (staged)")

    broken = run_source(source, conn)
    print(f"3. run             state={broken['state']} records={broken['records']} "
          f"incident={broken['incident_id']}")

    outcome = attempt_repair(
        source,
        conn,
        golden.load(source).records,
        broken_snapshot=ROOT / broken["snapshot"],
        healthy_snapshot=healthy_snapshot_path(source.id),
    )
    print(f"4. gate            {outcome.decision} accuracy={outcome.accuracy:.4f} "
          f"applied={outcome.applied} mttr={outcome.mttr_seconds}s")

    after = run_source(source, conn)
    print(f"5. run             state={after['state']} records={after['records']} "
          f"extractor={after['extractor']}")

    clear_injection(conn, source.id)
    revert(source, conn, "books.v1")
    restored = run_source(source, conn)
    print(f"6. revert+run      state={restored['state']} records={restored['records']} "
          f"extractor={restored['extractor']}")

    meta = export_all(conn, ROOT / out_dir)
    print(f"7. export          {meta}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "data"))
