"""Sentinel command line.

Exit codes: 0 ok, 2 refused or invalid config (ACCEPTANCE A9), 1 runtime failure.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import db as store
from . import golden
from .config import ConfigError, RefusalError, get_source, load_sources
from .pipeline import clear_injection, inject_drift, run_source


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_run(args) -> int:
    source = get_source(args.source)
    conn = store.connect()
    with golden.guard(source):
        result = run_source(source, conn)
    _print(result)
    conn.close()
    return 0


def cmd_inject(args) -> int:
    source = get_source(args.source)
    conn = store.connect()
    inject_drift(conn, source.id)
    conn.close()
    print(f"staged demo: injected layout rev 2 on '{source.id}' (incidents opened now are staged)")
    return 0


def cmd_clear(args) -> int:
    source = get_source(args.source)
    conn = store.connect()
    clear_injection(conn, source.id)
    conn.close()
    print(f"cleared injection on '{source.id}'")
    return 0


def cmd_state(args) -> int:
    conn = store.connect()
    out = []
    for source in load_sources():
        state = store.source_state(conn, source.id)
        incident = store.active_incident(conn, source.id)
        out.append(
            {
                "source": source.id,
                "state": state["state"] if state else "UNKNOWN",
                "drift_score": state["drift_score"] if state else None,
                "last_run_id": state["last_run_id"] if state else None,
                "active_incident": incident["id"] if incident else None,
                "staged": bool(incident["staged"]) if incident else False,
            }
        )
    conn.close()
    _print(out)
    return 0


def cmd_golden(args) -> int:
    source = get_source(args.source)
    try:
        gs = golden.load(source)
    except golden.GoldenMissing as exc:
        print(f"UNVERIFIED: {exc}", file=sys.stderr)
        return 1
    except golden.GoldenInvalid as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    golden.verify_seal(source, gs)
    _print(
        {
            "source": source.id,
            "path": str(gs.path),
            "records": len(gs),
            "sha256": gs.sha256,
            "mtime_ns": gs.mtime_ns,
            "sealed": golden.fingerprint_file(source).exists(),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel", description="drift + gated repair")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one source once")
    run.add_argument("--source", default="books")
    run.set_defaults(func=cmd_run)

    inject = sub.add_parser("inject", help="staged demo: break one source deliberately")
    inject.add_argument("--source", default="books")
    inject.set_defaults(func=cmd_inject)

    clear = sub.add_parser("clear", help="remove the injected breakage")
    clear.add_argument("--source", default="books")
    clear.set_defaults(func=cmd_clear)

    state = sub.add_parser("state", help="per-source state")
    state.set_defaults(func=cmd_state)

    g = sub.add_parser("golden", help="verify the frozen golden set")
    g.add_argument("--source", default="books")
    g.set_defaults(func=cmd_golden)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RefusalError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
