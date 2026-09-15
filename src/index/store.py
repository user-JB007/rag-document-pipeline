"""Index stage: build or rebuild a vector store under data/index/.

Default backend is a NumPy cosine index (no native compile deps).
Optional backends: chroma, faiss (install those packages to enable).

Inputs:
  - chunks.jsonl + embeddings.npy from the embed stage
Outputs:
  - Persistable index under data/index/ (idempotent full rebuild)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from src.models import Chunk


def _load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks


def _chunk_records(chunks: list[Chunk]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "title": c.title,
            "source_path": c.source_path,
            "text": c.text,
            "chunk_index": c.chunk_index,
            "ingested_at": c.ingested_at,
        }
        for c in chunks
    ]


def _reset_dir(index_dir: str | Path) -> Path:
    index_path = Path(index_dir)
    if index_path.exists():
        shutil.rmtree(index_path)
    index_path.mkdir(parents=True, exist_ok=True)
    return index_path


def build_numpy_index(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    index_dir: str | Path,
) -> Path:
    """Rebuild a NumPy cosine index (normalized vectors + chunk sidecar)."""
    index_path = _reset_dir(index_dir)
    matrix = embeddings.astype(np.float32)
    # Ensure L2-normalized for cosine via dot product
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    np.save(index_path / "vectors.npy", matrix)
    with (index_path / "chunks.json").open("w", encoding="utf-8") as fh:
        json.dump(_chunk_records(chunks), fh)
    manifest = {
        "backend": "numpy",
        "count": len(chunks),
        "dimensions": int(matrix.shape[1]) if matrix.size else 0,
        "distance": "cosine",
    }
    with (index_path / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return index_path


def build_chroma_index(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    index_dir: str | Path,
    collection_name: str = "knowledge_docs",
) -> Path:
    """Rebuild a Chroma persistent collection from scratch."""
    import chromadb
    from chromadb.config import Settings

    index_path = _reset_dir(index_dir)
    client = chromadb.PersistentClient(
        path=str(index_path),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "doc_id": c.doc_id,
            "title": c.title,
            "source_path": c.source_path,
            "chunk_index": c.chunk_index,
            "ingested_at": c.ingested_at,
        }
        for c in chunks
    ]
    batch = 100
    for i in range(0, len(ids), batch):
        collection.add(
            ids=ids[i : i + batch],
            embeddings=embeddings[i : i + batch].tolist(),
            documents=documents[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )
    with (index_path / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "backend": "chroma",
                "collection_name": collection_name,
                "count": len(ids),
                "dimensions": int(embeddings.shape[1]) if embeddings.size else 0,
            },
            fh,
            indent=2,
        )
    return index_path


def build_faiss_index(
    chunks: list[Chunk],
    embeddings: np.ndarray,
    index_dir: str | Path,
) -> Path:
    """Rebuild a FAISS IndexFlatIP (cosine via normalized vectors) with sidecar metadata."""
    try:
        import faiss  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "faiss-cpu is required for backend=faiss. Install faiss-cpu or use backend=numpy."
        ) from exc

    index_path = _reset_dir(index_dir)
    dim = int(embeddings.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, str(index_path / "faiss.index"))
    with (index_path / "chunks.json").open("w", encoding="utf-8") as fh:
        json.dump(_chunk_records(chunks), fh)
    with (index_path / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump({"backend": "faiss", "count": len(chunks), "dimensions": dim}, fh, indent=2)
    return index_path


def run_index(
    cfg: dict[str, Any],
    chunks: list[Chunk] | None = None,
    embeddings: np.ndarray | None = None,
) -> Path:
    """Execute index stage using pipeline config. Idempotent full rebuild."""
    processed = Path(cfg["paths"]["processed"])
    index_dir = Path(cfg["paths"]["index"])
    if chunks is None:
        chunks = _load_chunks(processed / "chunks.jsonl")
    if embeddings is None:
        embeddings = np.load(processed / "embeddings.npy")
    if len(chunks) != len(embeddings):
        raise ValueError(f"chunk/embedding count mismatch: {len(chunks)} vs {len(embeddings)}")

    backend = cfg.get("index", {}).get("backend", "numpy")
    if backend == "faiss":
        return build_faiss_index(chunks, embeddings, index_dir)
    if backend == "chroma":
        return build_chroma_index(
            chunks,
            embeddings,
            index_dir,
            collection_name=cfg.get("index", {}).get("collection_name", "knowledge_docs"),
        )
    return build_numpy_index(chunks, embeddings, index_dir)
