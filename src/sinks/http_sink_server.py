"""Landing FastAPI for RAG ask/eval result POSTs.

  uvicorn src.sinks.http_sink_server:app --host 127.0.0.1 --port 8089
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "data" / "landing"
LANDING.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="rag-document-pipeline sink", version="1.0.0")


def _save(payload: Any, route: str) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = LANDING / f"{ts}_{route.replace('/', '_')}.json"
    record = {
        "received_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "route": route,
        "payload": payload,
    }
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "id": path.stem, "path": str(path)}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(request: Request) -> JSONResponse:
    return JSONResponse(_save(await request.json(), "/ingest"))


@app.post("/events")
async def events(request: Request) -> JSONResponse:
    return JSONResponse(_save(await request.json(), "/events"))
