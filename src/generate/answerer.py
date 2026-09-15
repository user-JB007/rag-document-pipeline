"""Generate stage: produce an answer grounded in retrieved context.

Default mode is offline extractive/template answering (no paid API).
Optional mode uses an OpenAI-compatible HTTP API when env vars are set.

Inputs:
  - Query string + List[RetrievalHit]
Outputs:
  - Answer dict: answer, citations, mode, context_used
"""

from __future__ import annotations

import os
import re
from typing import Any

from src.models import RetrievalHit


def _select_context(hits: list[RetrievalHit], max_chars: int) -> list[RetrievalHit]:
    selected: list[RetrievalHit] = []
    used = 0
    for hit in hits:
        if used + len(hit.text) > max_chars and selected:
            break
        selected.append(hit)
        used += len(hit.text)
    return selected


def _sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _keyword_overlap(query: str, sentence: str) -> float:
    q = {w.lower() for w in re.findall(r"[a-zA-Z0-9']+", query) if len(w) > 2}
    s = {w.lower() for w in re.findall(r"[a-zA-Z0-9']+", sentence) if len(w) > 2}
    if not q or not s:
        return 0.0
    return len(q & s) / len(q)


def extractive_answer(query: str, hits: list[RetrievalHit], max_context_chars: int = 3500) -> dict[str, Any]:
    """Build an answer from the most relevant sentences in retrieved chunks."""
    selected = _select_context(hits, max_context_chars)
    if not selected:
        return {
            "answer": "No relevant documents were retrieved for this question.",
            "citations": [],
            "mode": "extractive",
            "context_used": [],
        }

    scored: list[tuple[float, str, RetrievalHit]] = []
    for hit in selected:
        for sent in _sentence_split(hit.text):
            if len(sent) < 25:
                continue
            scored.append((_keyword_overlap(query, sent) + 0.15 * hit.score, sent, hit))
    scored.sort(key=lambda x: x[0], reverse=True)

    seen: set[str] = set()
    chosen: list[tuple[str, RetrievalHit]] = []
    for score, sent, hit in scored:
        key = sent.lower()
        if key in seen:
            continue
        if score < 0.12 and chosen:
            continue
        seen.add(key)
        chosen.append((sent, hit))
        if len(chosen) >= 4:
            break

    if not chosen:
        # Fall back to leading text from top hit
        top = selected[0]
        chosen = [(top.text[:400].rsplit(" ", 1)[0] + "...", top)]

    answer_body = " ".join(s for s, _ in chosen)
    citations = []
    context_used = []
    for hit in selected:
        citations.append(
            {
                "doc_id": hit.doc_id,
                "title": hit.title,
                "source_path": hit.source_path,
                "chunk_id": hit.chunk_id,
                "score": round(hit.score, 4),
            }
        )
        context_used.append({"chunk_id": hit.chunk_id, "title": hit.title, "score": round(hit.score, 4)})

    preamble = (
        f"Based on {len(selected)} retrieved passage(s) from the knowledge base:\n\n"
    )
    return {
        "answer": preamble + answer_body,
        "citations": citations,
        "mode": "extractive",
        "context_used": context_used,
    }


def openai_compatible_answer(
    query: str,
    hits: list[RetrievalHit],
    max_context_chars: int = 3500,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Call an OpenAI-compatible chat completions endpoint with retrieved context."""
    import httpx

    selected = _select_context(hits, max_context_chars)
    if not selected:
        return extractive_answer(query, hits, max_context_chars)

    context_blocks = []
    for i, hit in enumerate(selected, 1):
        context_blocks.append(
            f"[{i}] title={hit.title} doc_id={hit.doc_id}\n{hit.text}"
        )
    context = "\n\n".join(context_blocks)
    system = (
        "You answer questions using only the provided knowledge-base passages. "
        "If the passages do not contain the answer, say you cannot find it. "
        "Cite passage numbers like [1] when making claims."
    )
    user = f"Passages:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for openai_compatible mode")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    citations = [
        {
            "doc_id": h.doc_id,
            "title": h.title,
            "source_path": h.source_path,
            "chunk_id": h.chunk_id,
            "score": round(h.score, 4),
        }
        for h in selected
    ]
    return {
        "answer": text,
        "citations": citations,
        "mode": "openai_compatible",
        "context_used": [{"chunk_id": h.chunk_id, "title": h.title, "score": round(h.score, 4)} for h in selected],
    }


def generate_answer(cfg: dict[str, Any], query: str, hits: list[RetrievalHit]) -> dict[str, Any]:
    """Execute generate stage using configured mode."""
    gen_cfg = cfg.get("generate", {})
    mode = gen_cfg.get("mode", "extractive")
    max_chars = int(gen_cfg.get("max_context_chars", 3500))

    # Auto-upgrade to API mode when key is present and mode requests it
    if mode == "openai_compatible" or (
        mode == "extractive" and os.getenv("OPENAI_API_KEY") and os.getenv("RAG_FORCE_OPENAI") == "1"
    ):
        if mode == "openai_compatible":
            return openai_compatible_answer(query, hits, max_context_chars=max_chars)

    return extractive_answer(query, hits, max_context_chars=max_chars)
