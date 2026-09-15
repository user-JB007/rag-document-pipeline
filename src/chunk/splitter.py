"""Chunk stage: split documents into overlapping windows with stable chunk_ids.

Inputs:
  - List[Document] (or documents.jsonl)
Outputs:
  - List[Chunk] with chunk_id = sha1(doc_id + index + text_prefix)
  - Optional JSONL dump under data/processed/chunks.jsonl
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.models import Chunk, Document


def _stable_chunk_id(doc_id: str, index: int, text: str) -> str:
    payload = f"{doc_id}|{index}|{text[:64]}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Character-window splitter with overlap. Prefers paragraph boundaries when close."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    cleaned = text.replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + size, length)
        if end < length:
            # Prefer breaking on paragraph or sentence near the window end
            window = cleaned[start:end]
            break_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if break_at > size * 0.4:
                end = start + break_at + (1 if window[break_at] == "." else 0)
                if window[break_at] == ".":
                    end = start + break_at + 1
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(0, end - overlap)
    return chunks


def chunk_documents(
    documents: list[Document],
    size: int = 500,
    overlap: int = 80,
    min_chars: int = 40,
) -> list[Chunk]:
    """Chunk all documents into overlapping windows."""
    results: list[Chunk] = []
    for doc in documents:
        pieces = split_text(doc.text, size=size, overlap=overlap)
        for idx, piece in enumerate(pieces):
            if len(piece) < min_chars:
                continue
            results.append(
                Chunk(
                    chunk_id=_stable_chunk_id(doc.doc_id, idx, piece),
                    doc_id=doc.doc_id,
                    title=doc.title,
                    source_path=doc.source_path,
                    text=piece,
                    chunk_index=idx,
                    ingested_at=doc.ingested_at,
                    metadata={"extension": doc.metadata.get("extension")},
                )
            )
    return results


def persist_chunks(chunks: list[Chunk], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    return out


def load_documents_jsonl(path: str | Path) -> list[Document]:
    docs: list[Document] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                docs.append(Document.from_dict(json.loads(line)))
    return docs


def run_chunk(cfg: dict[str, Any], documents: list[Document] | None = None) -> list[Chunk]:
    """Execute chunk stage using pipeline config."""
    processed = Path(cfg["paths"]["processed"])
    if documents is None:
        documents = load_documents_jsonl(processed / "documents.jsonl")
    chunk_cfg = cfg.get("chunk", {})
    chunks = chunk_documents(
        documents,
        size=int(chunk_cfg.get("size", 500)),
        overlap=int(chunk_cfg.get("overlap", 80)),
        min_chars=int(chunk_cfg.get("min_chars", 40)),
    )
    persist_chunks(chunks, processed / "chunks.jsonl")
    return chunks
