"""Load and expose pipeline configuration from YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "pipeline.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Return pipeline config as a dict. Honors RAG_CONFIG env override."""
    cfg_path = Path(path or os.getenv("RAG_CONFIG", DEFAULT_CONFIG))
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    # Resolve relative paths against repo root
    for key, value in list(data.get("paths", {}).items()):
        p = Path(value)
        if not p.is_absolute():
            data["paths"][key] = str(ROOT / p)
    return data


def ensure_dirs(cfg: dict[str, Any]) -> None:
    """Create processed and index directories if missing."""
    for key in ("processed", "index"):
        Path(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
