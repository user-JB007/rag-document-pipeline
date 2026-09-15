"""API sink: POST ask/eval results to local FastAPI sink + optional JSONPlaceholder."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.integrations.http_client import post_json

ROOT = Path(__file__).resolve().parents[2]


def _sink_cfg(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    api_sink = (cfg or {}).get("api_sink") or {}
    return {
        "local_url": os.getenv(
            "SINK_API_URL", api_sink.get("local_url", "http://127.0.0.1:8089/ingest")
        ),
        "external_url": os.getenv(
            "EXTERNAL_SINK_URL",
            api_sink.get("external_url", "https://jsonplaceholder.typicode.com/posts"),
        ),
        "timeout": float(os.getenv("API_HTTP_TIMEOUT", api_sink.get("timeout", 20))),
        "retries": int(os.getenv("API_HTTP_RETRIES", api_sink.get("retries", 3))),
    }


def _write_receipt(name: str, payload: dict[str, Any], response: Any) -> Path:
    receipts = ROOT / "data" / "sink_receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = receipts / f"{ts}_{name}.json"
    path.write_text(
        json.dumps({"request": payload, "response": response}, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def build_results_payload(cfg: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "pipeline": "rag-document-pipeline",
        "pushed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    eval_path = Path(cfg["paths"].get("eval_results", ROOT / "eval" / "results.json"))
    if eval_path.exists():
        try:
            payload["eval"] = json.loads(eval_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload["eval_raw"] = eval_path.read_text(encoding="utf-8")[:2000]
    if extra:
        payload.update(extra)
    return payload


def push_results(
    cfg: dict[str, Any],
    *,
    payload: dict[str, Any] | None = None,
    post_local: bool = True,
    post_external: bool = True,
) -> dict[str, Any]:
    scfg = _sink_cfg(cfg)
    body = payload or build_results_payload(cfg)
    result: dict[str, Any] = {"deliveries": {}}

    if post_local:
        try:
            resp = post_json(scfg["local_url"], body, timeout=scfg["timeout"], retries=scfg["retries"])
            receipt = _write_receipt("local", body, resp)
            result["deliveries"]["local"] = {
                "ok": True,
                "url": scfg["local_url"],
                "receipt": str(receipt),
                "response": resp,
            }
        except Exception as exc:
            landing = ROOT / "data" / "landing"
            landing.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            fallback = landing / f"rag_results_{ts}.json"
            fallback.write_text(json.dumps(body, indent=2, default=str), encoding="utf-8")
            result["deliveries"]["local"] = {"ok": False, "error": str(exc), "fallback_file": str(fallback)}

    if post_external:
        try:
            ext_body = {
                "title": "rag-document-pipeline results",
                "body": json.dumps(body, default=str)[:5000],
                "userId": 1,
            }
            resp = post_json(scfg["external_url"], ext_body, timeout=scfg["timeout"], retries=scfg["retries"])
            receipt = _write_receipt("external_jsonplaceholder", ext_body, resp)
            result["deliveries"]["external"] = {
                "ok": True,
                "url": scfg["external_url"],
                "receipt": str(receipt),
                "response": resp,
            }
        except Exception as exc:
            result["deliveries"]["external"] = {"ok": False, "error": str(exc)}

    return result
