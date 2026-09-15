"""Ingest stage: load PDF/Markdown/TXT from source (+ optional remote) directories.

Inputs:
  - Directory of source documents (extensions from config)
  - Optional data/remote_docs/ from pull_remote_docs
Outputs:
  - List[Document] with doc_id, title, source_path, ingested_at, text
  - Optional JSONL dump under data/processed/documents.jsonl
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import Document


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        return stripped[:120]
    return fallback


def _doc_id_for(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", path.stem).strip("-").lower()
    return f"{stem}-{digest}"


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        parts.append(extracted)
    return "\n".join(parts)


def load_documents(
    source_dir: str | Path,
    extensions: list[str] | None = None,
    *,
    source_label: str = "local",
) -> list[Document]:
    """Load and normalize all supported documents under source_dir."""
    source = Path(source_dir)
    if not source.exists():
        return []

    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in (extensions or [".md", ".txt", ".pdf"])}
    ingested_at = _utc_now()
    documents: list[Document] = []

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(".meta.json") or path.name == "manifest.json":
            continue
        if path.suffix.lower() not in exts:
            continue
        if path.suffix.lower() == ".pdf":
            text = _read_pdf(path)
        else:
            text = _read_text_file(path)
        text = text.strip()
        if not text:
            continue
        try:
            rel_path = str(path.resolve().relative_to(Path(__file__).resolve().parents[2]))
        except ValueError:
            rel_path = str(path)
        doc = Document(
            doc_id=_doc_id_for(path),
            title=_title_from_text(text, path.stem),
            source_path=rel_path,
            text=text,
            ingested_at=ingested_at,
            metadata={
                "extension": path.suffix.lower(),
                "bytes": path.stat().st_size,
                "source_label": source_label,
            },
        )
        documents.append(doc)
    return documents


def persist_documents(documents: list[Document], output_path: str | Path) -> Path:
    """Write documents as JSONL for downstream stages."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for doc in documents:
            fh.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
    return out


def run_ingest(cfg: dict[str, Any]) -> list[Document]:
    """Execute ingest stage using pipeline config (local + optional remote docs)."""
    exts = cfg.get("ingest", {}).get("extensions")
    docs = load_documents(cfg["paths"]["source_docs"], exts, source_label="local")
    include_remote = bool(cfg.get("ingest", {}).get("include_remote_docs", True))
    remote_dir = cfg["paths"].get("remote_docs")
    if include_remote and remote_dir and Path(remote_dir).exists():
        remote_docs = load_documents(remote_dir, exts, source_label="http")
        docs.extend(remote_docs)
    # Deduplicate by doc_id
    seen: set[str] = set()
    unique: list[Document] = []
    for d in docs:
        if d.doc_id in seen:
            continue
        seen.add(d.doc_id)
        unique.append(d)
    persist_documents(unique, Path(cfg["paths"]["processed"]) / "documents.jsonl")
    return unique
