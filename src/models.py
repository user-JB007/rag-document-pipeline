"""Shared data models for documents, chunks, and retrieval hits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Document:
    """Normalized source document after ingest."""

    doc_id: str
    title: str
    source_path: str
    text: str
    ingested_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        return cls(**data)


@dataclass
class Chunk:
    """Text chunk with stable identity and parent document metadata."""

    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str
    chunk_index: int
    ingested_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        return cls(**data)


@dataclass
class RetrievalHit:
    """A ranked retrieval result with similarity score."""

    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
