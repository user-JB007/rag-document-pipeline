"""Retrieve stage: top-k similarity search with optional metadata filters.

Inputs:
  - Query string, built vector index, embedding model
Outputs:
  - List[RetrievalHit] with scores (higher = more similar for cosine)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from src.models import RetrievalHit


@lru_cache(maxsize=2)
def _load_embedder(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device=device)


def _embed_query(query: str, model_name: str, device: str = "cpu") -> np.ndarray:
    model = _load_embedder(model_name, device)
    vec = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    return vec[0].astype(np.float32)


def _read_manifest(index_dir: Path) -> dict[str, Any]:
    path = index_dir / "manifest.json"
    if not path.exists():
        return {"backend": "numpy"}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _filter_where(item: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    return all(str(item.get(k)) == str(v) for k, v in where.items())


def retrieve_numpy(
    query: str,
    index_dir: str | Path,
    model_name: str,
    top_k: int = 4,
    device: str = "cpu",
    where: dict[str, Any] | None = None,
    score_threshold: float = 0.0,
) -> list[RetrievalHit]:
    index_path = Path(index_dir)
    vectors = np.load(index_path / "vectors.npy")
    with (index_path / "chunks.json").open(encoding="utf-8") as fh:
        stored = json.load(fh)
    qvec = _embed_query(query, model_name, device)
    scores = vectors @ qvec
    # Rank all, then apply metadata filter
    order = np.argsort(-scores)
    hits: list[RetrievalHit] = []
    for idx in order:
        item = stored[int(idx)]
        if not _filter_where(item, where):
            continue
        sim = float(scores[int(idx)])
        if sim < score_threshold:
            continue
        hits.append(
            RetrievalHit(
                chunk_id=item["chunk_id"],
                doc_id=item["doc_id"],
                title=item["title"],
                source_path=item["source_path"],
                text=item["text"],
                score=sim,
                metadata={"chunk_index": item.get("chunk_index")},
            )
        )
        if len(hits) >= top_k:
            break
    return hits


def retrieve_chroma(
    query: str,
    index_dir: str | Path,
    model_name: str,
    top_k: int = 4,
    collection_name: str = "knowledge_docs",
    device: str = "cpu",
    where: dict[str, Any] | None = None,
    score_threshold: float = 0.0,
) -> list[RetrievalHit]:
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(index_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(name=collection_name)
    qvec = _embed_query(query, model_name, device).tolist()
    kwargs: dict[str, Any] = {
        "query_embeddings": [qvec],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    result = collection.query(**kwargs)

    hits: list[RetrievalHit] = []
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
        score = 1.0 - float(dist)
        if score < score_threshold:
            continue
        hits.append(
            RetrievalHit(
                chunk_id=chunk_id,
                doc_id=str(meta.get("doc_id", "")),
                title=str(meta.get("title", "")),
                source_path=str(meta.get("source_path", "")),
                text=text,
                score=score,
                metadata=dict(meta),
            )
        )
    return hits


def retrieve_faiss(
    query: str,
    index_dir: str | Path,
    model_name: str,
    top_k: int = 4,
    device: str = "cpu",
    where: dict[str, Any] | None = None,
    score_threshold: float = 0.0,
) -> list[RetrievalHit]:
    import faiss  # type: ignore

    index_path = Path(index_dir)
    index = faiss.read_index(str(index_path / "faiss.index"))
    with (index_path / "chunks.json").open(encoding="utf-8") as fh:
        stored = json.load(fh)
    qvec = np.asarray([_embed_query(query, model_name, device)], dtype=np.float32)
    # Over-fetch if filtering
    fetch = top_k * 5 if where else top_k
    scores, indices = index.search(qvec, min(fetch, len(stored)))
    hits: list[RetrievalHit] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        item = stored[int(idx)]
        if not _filter_where(item, where):
            continue
        sim = float(score)
        if sim < score_threshold:
            continue
        hits.append(
            RetrievalHit(
                chunk_id=item["chunk_id"],
                doc_id=item["doc_id"],
                title=item["title"],
                source_path=item["source_path"],
                text=item["text"],
                score=sim,
                metadata={"chunk_index": item.get("chunk_index")},
            )
        )
        if len(hits) >= top_k:
            break
    return hits


def retrieve(
    cfg: dict[str, Any],
    query: str,
    top_k: int | None = None,
    where: dict[str, Any] | None = None,
) -> list[RetrievalHit]:
    """Execute retrieve stage for a single query."""
    index_cfg = cfg.get("index", {})
    retrieve_cfg = cfg.get("retrieve", {})
    embed_cfg = cfg.get("embed", {})
    k = top_k if top_k is not None else int(retrieve_cfg.get("top_k", 4))
    index_dir = Path(cfg["paths"]["index"])
    manifest = _read_manifest(index_dir)
    backend = manifest.get("backend") or index_cfg.get("backend", "numpy")
    common = dict(
        query=query,
        index_dir=index_dir,
        model_name=embed_cfg.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
        top_k=k,
        device=embed_cfg.get("device", "cpu"),
        where=where,
        score_threshold=float(retrieve_cfg.get("score_threshold", 0.0)),
    )
    if backend == "faiss":
        return retrieve_faiss(**common)
    if backend == "chroma":
        return retrieve_chroma(
            **common,
            collection_name=index_cfg.get("collection_name", "knowledge_docs"),
        )
    return retrieve_numpy(**common)
