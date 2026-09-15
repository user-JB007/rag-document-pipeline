"""FastAPI service exposing /health and /ask over the built RAG index.

Start:
  uvicorn src.api.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import load_config
from src.pipeline import ask

app = FastAPI(title="RAG Document Pipeline", version="1.0.0")
_cfg = load_config()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    top_k: int | None = Field(default=None, ge=1, le=20)
    doc_id: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    mode: str
    citations: list[dict[str, Any]]
    context_used: list[dict[str, Any]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(body: AskRequest) -> AskResponse:
    try:
        where = {"doc_id": body.doc_id} if body.doc_id else None
        result = ask(_cfg, body.question, top_k=body.top_k, where=where)
    except Exception as exc:  # noqa: BLE001 — surface as HTTP 500 with message
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(
        question=result["question"],
        answer=result["answer"],
        mode=result["mode"],
        citations=result.get("citations", []),
        context_used=result.get("context_used", []),
    )
