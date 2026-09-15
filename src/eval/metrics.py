"""Evaluate stage: run a golden Q&A set and compute retrieval/answer heuristics.

Inputs:
  - eval/questions.json (question, expected_doc_ids, expected_keywords)
  - Built index + retrieve/generate stack
Outputs:
  - eval/results.json with per-question detail and aggregate metrics
    (hit@k, keyword_recall, context_relevance, faithfulness_lite)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.generate.answerer import generate_answer
from src.retrieve.searcher import retrieve


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_hits(answer: str, keywords: list[str]) -> tuple[int, int]:
    norm = _normalize(answer)
    found = 0
    for kw in keywords:
        if _normalize(kw) in norm:
            found += 1
    return found, len(keywords)


def _context_relevance(query: str, contexts: list[str]) -> float:
    q_tokens = {w for w in re.findall(r"[a-zA-Z0-9']+", query.lower()) if len(w) > 2}
    if not q_tokens or not contexts:
        return 0.0
    scores = []
    for ctx in contexts:
        c_tokens = {w for w in re.findall(r"[a-zA-Z0-9']+", ctx.lower()) if len(w) > 2}
        if not c_tokens:
            scores.append(0.0)
        else:
            scores.append(len(q_tokens & c_tokens) / len(q_tokens))
    return sum(scores) / len(scores)


def _faithfulness_lite(answer: str, contexts: list[str]) -> float:
    """Fraction of answer content words that appear in retrieved context (lightweight proxy)."""
    answer_tokens = {w for w in re.findall(r"[a-zA-Z0-9']+", answer.lower()) if len(w) > 3}
    if not answer_tokens:
        return 0.0
    ctx_tokens = {w for w in re.findall(r"[a-zA-Z0-9']+", " ".join(contexts).lower()) if len(w) > 3}
    if not ctx_tokens:
        return 0.0
    return len(answer_tokens & ctx_tokens) / len(answer_tokens)


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    return data


def run_eval(cfg: dict[str, Any]) -> dict[str, Any]:
    """Execute evaluation over the golden question set."""
    questions = load_questions(cfg["paths"]["eval_questions"])
    top_k = int(cfg.get("eval", {}).get("top_k", cfg.get("retrieve", {}).get("top_k", 4)))
    hit_threshold = float(cfg.get("eval", {}).get("hit_threshold", 0.25))

    per_q: list[dict[str, Any]] = []
    hits_at_k = 0
    keyword_recall_scores: list[float] = []
    relevance_scores: list[float] = []
    faith_scores: list[float] = []

    for item in questions:
        qid = item.get("id", item.get("question", "")[:40])
        question = item["question"]
        expected_docs = set(item.get("expected_doc_ids", []) or item.get("expected_doc_id_substrings", []))
        expected_keywords = item.get("expected_keywords", [])

        hits = retrieve(cfg, question, top_k=top_k)
        retrieved_docs = {h.doc_id for h in hits}
        retrieved_titles = {h.title.lower() for h in hits}
        retrieved_paths = {h.source_path.lower() for h in hits}

        # Hit if any expected doc id substring matches retrieved doc_id/title/path
        hit = False
        if expected_docs:
            for exp in expected_docs:
                el = exp.lower()
                if any(el in d.lower() for d in retrieved_docs):
                    hit = True
                    break
                if any(el in t for t in retrieved_titles):
                    hit = True
                    break
                if any(el in p for p in retrieved_paths):
                    hit = True
                    break
        else:
            hit = bool(hits) and hits[0].score >= hit_threshold

        if hit:
            hits_at_k += 1

        answer_payload = generate_answer(cfg, question, hits)
        answer_text = answer_payload["answer"]
        contexts = [h.text for h in hits]

        found, total_kw = _keyword_hits(answer_text + " " + " ".join(contexts), expected_keywords)
        kw_recall = (found / total_kw) if total_kw else 0.0
        keyword_recall_scores.append(kw_recall)

        rel = _context_relevance(question, contexts)
        faith = _faithfulness_lite(answer_text, contexts)
        relevance_scores.append(rel)
        faith_scores.append(faith)

        per_q.append(
            {
                "id": qid,
                "question": question,
                "hit_at_k": hit,
                "keyword_recall": round(kw_recall, 4),
                "context_relevance": round(rel, 4),
                "faithfulness_lite": round(faith, 4),
                "top_scores": [round(h.score, 4) for h in hits],
                "retrieved_doc_ids": [h.doc_id for h in hits],
                "retrieved_titles": [h.title for h in hits],
                "answer_preview": answer_text[:280],
            }
        )

    n = max(len(questions), 1)
    summary = {
        "num_questions": len(questions),
        "hit_at_k": round(hits_at_k / n, 4),
        "keyword_recall": round(sum(keyword_recall_scores) / n, 4),
        "context_relevance": round(sum(relevance_scores) / n, 4),
        "faithfulness_lite": round(sum(faith_scores) / n, 4),
        "top_k": top_k,
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    results = {"summary": summary, "questions": per_q}
    out = Path(cfg["paths"]["eval_results"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    return results
