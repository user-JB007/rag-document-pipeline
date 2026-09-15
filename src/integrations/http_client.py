"""HTTP helpers with timeouts and simple retries (httpx)."""

from __future__ import annotations

import time
from typing import Any

import httpx

DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.8


def request(
    method: str,
    url: str,
    *,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(method.upper(), url, json=json_body, headers=headers)
            if resp.status_code >= 500 and attempt < retries:
                time.sleep(backoff * attempt)
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(backoff * attempt)
    assert last_exc is not None
    raise last_exc


def get_text(url: str, **kwargs: Any) -> tuple[str, str]:
    """Return (text, content_type)."""
    resp = request("GET", url, **kwargs)
    ctype = resp.headers.get("content-type", "text/plain")
    return resp.text, ctype


def get_json(url: str, **kwargs: Any) -> Any:
    return request("GET", url, **kwargs).json()


def post_json(url: str, json_body: Any, **kwargs: Any) -> Any:
    resp = request("POST", url, json_body=json_body, headers={"Content-Type": "application/json"}, **kwargs)
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text[:500]}
