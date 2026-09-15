"""Smoke tests for remote doc source and result sink."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.config import load_config
from src.integrations.api_sink import push_results
from src.integrations.http_client import get_text, post_json
from src.integrations.remote_docs import pull_remote_docs


def test_pull_remote_docs_mocked(tmp_path, monkeypatch):
    cfg = {
        "paths": {"remote_docs": str(tmp_path / "remote")},
        "sources": {"http_documents": ["https://example.com/doc.md"]},
        "api_source": {"timeout": 5, "retries": 1},
    }
    with patch("src.integrations.remote_docs.get_text", return_value=("# Hello\n\nWorld", "text/markdown")):
        result = pull_remote_docs(cfg, use_network=True)
    assert result["ok_count"] == 1
    assert any((tmp_path / "remote").glob("*.md"))


def test_push_results_external_mocked(tmp_path, monkeypatch):
    import src.integrations.api_sink as mod

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    cfg = {"paths": {}, "api_sink": {"local_url": "http://127.0.0.1:9/ingest", "external_url": "https://jsonplaceholder.typicode.com/posts"}}
    with patch("src.integrations.api_sink.post_json", return_value={"id": 7}):
        result = push_results(cfg, payload={"ask": {"question": "q", "answer": "a"}}, post_local=False, post_external=True)
    assert result["deliveries"]["external"]["ok"] is True


@pytest.mark.network
def test_live_remote_doc_optional():
    try:
        text, _ = get_text(
            "https://raw.githubusercontent.com/github/docs/main/content/get-started/using-github/github-flow.md",
            timeout=15,
            retries=1,
        )
    except Exception as exc:
        pytest.skip(f"network unavailable: {exc}")
    assert "GitHub" in text or "github" in text.lower() or len(text) > 100
