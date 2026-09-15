"""Embed stage: encode chunks with a local sentence-transformers model and persist vectors.

Inputs:
  - List[Chunk] (or chunks.jsonl)
Outputs:
  - embeddings.npy (float32 matrix aligned with chunks)
  - embedding_meta.json (model name, dimensions, chunk_ids)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.models import Chunk


def load_chunks_jsonl(path: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(Chunk.from_dict(json.loads(line)))
    return chunks


def encode_chunks(
    chunks: list[Chunk],
    model_name: str,
    batch_size: int = 32,
    device: str = "cpu",
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return (N, D) float32 embeddings and metadata for the given chunks."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device=device)
    texts = [c.text for c in chunks]
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    matrix = np.asarray(vectors, dtype=np.float32)
    meta = {
        "model_name": model_name,
        "dimensions": int(matrix.shape[1]) if matrix.size else 0,
        "count": int(matrix.shape[0]),
        "chunk_ids": [c.chunk_id for c in chunks],
        "device": device,
    }
    return matrix, meta


def persist_embeddings(matrix: np.ndarray, meta: dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "embeddings.npy", matrix)
    with (out / "embedding_meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return out


def run_embed(cfg: dict[str, Any], chunks: list[Chunk] | None = None) -> tuple[list[Chunk], np.ndarray, dict[str, Any]]:
    """Execute embed stage using pipeline config."""
    processed = Path(cfg["paths"]["processed"])
    if chunks is None:
        chunks = load_chunks_jsonl(processed / "chunks.jsonl")
    embed_cfg = cfg.get("embed", {})
    matrix, meta = encode_chunks(
        chunks,
        model_name=embed_cfg.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
        batch_size=int(embed_cfg.get("batch_size", 32)),
        device=embed_cfg.get("device", "cpu"),
    )
    persist_embeddings(matrix, meta, processed)
    return chunks, matrix, meta
