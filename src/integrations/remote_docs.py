"""API source: fetch remote HTTP documents listed in config into data/remote_docs/.

URLs come from config/pipeline.yaml `sources.http_documents`. Fetched files are
merged into ingest alongside data/source_docs/ (see loader.run_ingest).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.integrations.http_client import get_text

ROOT = Path(__file__).resolve().parents[2]


def _slug(url: str) -> str:
    path = urlparse(url).path.rsplit("/", 1)[-1] or "document"
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", path).strip("-").lower() or "document"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


def _ext_for(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".md", ".markdown", ".txt", ".json", ".html"):
        if path.endswith(ext):
            return ext
    ctype = (content_type or "").lower()
    if "json" in ctype:
        return ".json"
    if "markdown" in ctype or "md" in ctype:
        return ".md"
    if "html" in ctype:
        return ".html"
    return ".txt"


def pull_remote_docs(cfg: dict[str, Any], *, use_network: bool = True) -> dict[str, Any]:
    sources = cfg.get("sources", {}) or {}
    urls = list(sources.get("http_documents") or [])
    out_dir = Path(cfg["paths"].get("remote_docs", ROOT / "data" / "remote_docs"))
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    timeout = float(os.getenv("API_HTTP_TIMEOUT", (cfg.get("api_source") or {}).get("timeout", 20)))
    retries = int(os.getenv("API_HTTP_RETRIES", (cfg.get("api_source") or {}).get("retries", 3)))

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    if not urls:
        return {"fetched": 0, "files": [], "note": "no sources.http_documents configured"}

    for url in urls:
        entry: dict[str, Any] = {"url": url}
        try:
            if not use_network:
                raise ConnectionError("network disabled")
            text, ctype = get_text(url, timeout=timeout, retries=retries)
            ext = _ext_for(url, ctype)
            name = _slug(url) + ext
            path = out_dir / name
            if ext == ".json":
                # pretty-print if valid JSON
                try:
                    parsed = json.loads(text)
                    path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
                except json.JSONDecodeError:
                    path.write_text(text, encoding="utf-8")
            else:
                path.write_text(text, encoding="utf-8")
            meta = {
                "url": url,
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "content_type": ctype,
                "bytes": path.stat().st_size,
                "path": str(path),
            }
            (out_dir / (name + ".meta.json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
            entry.update(meta)
            entry["ok"] = True
            print(f"[pull_remote_docs] {url} -> {path}")
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = str(exc)
            errors.append(f"{url}: {exc}")
            # Offline: keep any previously downloaded file for this URL slug
            existing = list(out_dir.glob(f"{_slug(url)}.*"))
            existing = [p for p in existing if not p.name.endswith(".meta.json")]
            if existing:
                entry["fallback"] = str(existing[0])
                entry["ok"] = True
                print(f"[pull_remote_docs] network failed for {url}; reusing {existing[0]}")
            else:
                print(f"[pull_remote_docs] FAILED {url}: {exc}")
        results.append(entry)

    manifest = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": results,
        "ok_count": sum(1 for r in results if r.get("ok")),
        "errors": errors,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
