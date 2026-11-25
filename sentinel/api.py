"""FastAPI surface — SPEC §8. Local dev/tests only; the public demo is static (SPEC §14)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import db as store
from .config import ConfigError, RefusalError, get_source, load_sources
from .pipeline import inject_drift

app = FastAPI(title="Sentinel", version="0.1.0")


def _elapsed_seconds(start: str, end: str | None = None) -> int:
    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    finish = parse(end) if end else datetime.now(timezone.utc)
    return max(0, int((finish - parse(start)).total_seconds()))


@app.get("/health")
def health() -> dict:
    conn = store.connect()
    try:
        sources = []
        for source in load_sources():
            state = store.source_state(conn, source.id)
            last = conn.execute(
                "SELECT id, started_at, records, schema_failures FROM runs"
                " WHERE source = ? ORDER BY id DESC LIMIT 1",
                (source.id,),
            ).fetchone()
            sources.append(
                {
                    "source": source.id,
                    "state": state["state"] if state else "UNKNOWN",
                    "drift_score": state["drift_score"] if state else None,
                    "last_run": dict(last) if last else None,
                    "active_incident": state["active_incident_id"] if state else None,
                }
            )
        return {"sources": sources}
    finally:
        conn.close()


@app.get("/runs")
def runs(source: str = "books", limit: int = 20) -> dict:
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT id, source, started_at, finished_at, http_status, records,"
            " schema_failures, required_nulls, layout_rev, staged, extractor, error"
            " FROM runs WHERE source = ? ORDER BY id DESC LIMIT ?",
            (source, limit),
        ).fetchall()
        return {"runs": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/incidents")
def incidents() -> dict:
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC"
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["staged"] = bool(item["staged"])
            item["signals"] = json.loads(item["signals"]) if item["signals"] else {}
            item["duration_seconds"] = (
                item["mttr_seconds"]
                if item["mttr_seconds"] is not None
                else _elapsed_seconds(item["drift_detected_at"])
            )
            item["duration_label"] = "resolved" if item["mttr_seconds"] is not None else "ongoing"
            out.append(item)
        return {"incidents": out}
    finally:
        conn.close()


@app.get("/incidents/{incident_id}")
def incident(incident_id: int) -> dict:
    conn = store.connect()
    try:
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="incident not found")
        item = dict(row)
        item["staged"] = bool(item["staged"])
        item["signals"] = json.loads(item["signals"]) if item["signals"] else {}
        item["duration_seconds"] = (
            item["mttr_seconds"]
            if item["mttr_seconds"] is not None
            else _elapsed_seconds(item["drift_detected_at"])
        )
        return item
    finally:
        conn.close()


class InjectRequest(BaseModel):
    source: str = "books"


@app.post("/admin/inject-drift")
def admin_inject_drift(request: InjectRequest) -> dict:
    try:
        source = get_source(request.source)
    except (ConfigError, RefusalError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    conn = store.connect()
    try:
        inject_drift(conn, source.id)
        return {
            "source": source.id,
            "staged": True,
            "message": "layout rev 2 injected; the next run is a staged demo",
        }
    finally:
        conn.close()
