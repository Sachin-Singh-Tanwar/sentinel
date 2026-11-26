"""FastAPI surface — SPEC §8. Local dev/tests only; the public demo is static (SPEC §14)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db as store
from .config import ConfigError, RefusalError, get_source
from .export import build_board, build_incident, build_incidents, build_method
from .pipeline import inject_drift

app = FastAPI(title="Sentinel", version="0.1.0")

# Local dev only: the dashboard may be served from a different origin than the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    conn = store.connect()
    try:
        return build_board(conn)
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
        return build_incidents(conn)
    finally:
        conn.close()


@app.get("/incidents/{incident_id}")
def incident(incident_id: int) -> dict:
    conn = store.connect()
    try:
        payload = build_incident(conn, incident_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return payload
    finally:
        conn.close()


@app.get("/method")
def method() -> dict:
    conn = store.connect()
    try:
        return build_method(conn)
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
