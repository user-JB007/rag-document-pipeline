# Architecture

## Overview

The pipeline turns a directory of internal knowledge documents into a queryable retrieval index, then answers questions using retrieved passages.

```
source_docs → ingest → chunk → embed → index → retrieve → generate
                                              ↘ eval
```

## Stages

| Stage | Module | Responsibility |
|-------|--------|----------------|
| Ingest | `src/ingest/loader.py` | Load Markdown/TXT/PDF; assign `doc_id`, `title`, `source_path`, `ingested_at` |
| Chunk | `src/chunk/splitter.py` | Overlapping character windows; stable `chunk_id` |
| Embed | `src/embed/encoder.py` | Local `sentence-transformers` vectors; persist `.npy` |
| Index | `src/index/store.py` | Idempotent NumPy cosine (default), or Chroma/FAISS under `data/index/` |
| Retrieve | `src/retrieve/searcher.py` | Top-k cosine search; optional metadata `where` filter |
| Generate | `src/generate/answerer.py` | Offline extractive answerer, or OpenAI-compatible API |
| Evaluate | `src/eval/metrics.py` | Golden Q&A; hit@k, keyword recall, context relevance, faithfulness-lite |

## Persistence layout

```
data/
  source_docs/     # committed knowledge corpus
  processed/       # documents.jsonl, chunks.jsonl, embeddings.npy (generated)
  index/           # NumPy/Chroma/FAISS store + manifest.json (generated)
eval/
  questions.json   # golden set
  results.json     # last evaluation output
```

## Serving

- CLI: `python -m src.pipeline ask --question "..."`
- HTTP: FastAPI (`src/api/app.py`) with `POST /ask` and `GET /health`
- Batch: Airflow DAG `dags/rag_pipeline_dag.py` weekly rebuild + eval

## Generation modes

1. **extractive** (default) — ranks sentences from retrieved chunks by keyword overlap and similarity; works fully offline.
2. **openai_compatible** — set `generate.mode` to `openai_compatible` and provide `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`. Works with OpenAI or any compatible gateway.
