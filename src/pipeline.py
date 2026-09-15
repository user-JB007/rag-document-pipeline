"""CLI orchestration for the RAG document pipeline.

Stages: ingest → chunk → embed → index → ask → eval
Usage:
  python -m src.pipeline run --stage all
  python -m src.pipeline run --stage index
  python -m src.pipeline ask --question "..."
  python -m src.pipeline run --stage eval
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.chunk.splitter import run_chunk
from src.config import ensure_dirs, load_config
from src.embed.encoder import run_embed
from src.eval.metrics import run_eval
from src.generate.answerer import generate_answer
from src.index.store import run_index
from src.ingest.loader import run_ingest
from src.retrieve.searcher import retrieve


def build_index(cfg: dict[str, Any]) -> dict[str, Any]:
    """Run ingest → chunk → embed → index and return stage counts."""
    ensure_dirs(cfg)
    docs = run_ingest(cfg)
    chunks = run_chunk(cfg, docs)
    chunks, matrix, meta = run_embed(cfg, chunks)
    index_path = run_index(cfg, chunks, matrix)
    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "embedding_dim": meta.get("dimensions"),
        "index_path": str(index_path),
        "embed_model": meta.get("model_name"),
    }


def ask(cfg: dict[str, Any], question: str, top_k: int | None = None, where: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieve + generate for a single question."""
    hits = retrieve(cfg, question, top_k=top_k, where=where)
    payload = generate_answer(cfg, question, hits)
    payload["question"] = question
    payload["retrieval"] = [h.to_dict() for h in hits]
    return payload


def run_stage(cfg: dict[str, Any], stage: str, question: str | None = None) -> dict[str, Any]:
    ensure_dirs(cfg)
    stage = stage.lower()
    if stage == "all":
        stats = build_index(cfg)
        eval_results = run_eval(cfg)
        return {"build": stats, "eval_summary": eval_results["summary"]}
    if stage == "ingest":
        docs = run_ingest(cfg)
        return {"documents": len(docs)}
    if stage == "chunk":
        chunks = run_chunk(cfg)
        return {"chunks": len(chunks)}
    if stage == "embed":
        chunks, matrix, meta = run_embed(cfg)
        return {"chunks": len(chunks), "embedding_dim": meta.get("dimensions")}
    if stage == "index":
        # Rebuild full stack for a consistent index
        return build_index(cfg)
    if stage == "ask":
        if not question:
            raise SystemExit("--question is required for stage ask")
        return ask(cfg, question)
    if stage == "eval":
        return run_eval(cfg)
    raise SystemExit(f"Unknown stage: {stage}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="RAG document pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run one or more pipeline stages")
    run_p.add_argument(
        "--stage",
        default="all",
        choices=["all", "ingest", "chunk", "embed", "index", "ask", "eval"],
        help="Pipeline stage to execute",
    )
    run_p.add_argument("--question", default=None, help="Question for stage=ask")
    run_p.add_argument("--config", default=None, help="Path to pipeline.yaml")
    run_p.add_argument("--top-k", type=int, default=None)

    ask_p = sub.add_parser("ask", help="Ask a question against the built index")
    ask_p.add_argument("--question", required=True)
    ask_p.add_argument("--config", default=None)
    ask_p.add_argument("--top-k", type=int, default=None)
    ask_p.add_argument("--doc-id", default=None, help="Optional metadata filter on doc_id")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    if args.command == "ask" or (args.command == "run" and args.stage == "ask"):
        where = {"doc_id": args.doc_id} if getattr(args, "doc_id", None) else None
        result = ask(cfg, args.question, top_k=getattr(args, "top_k", None), where=where)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    result = run_stage(cfg, args.stage, question=getattr(args, "question", None))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
