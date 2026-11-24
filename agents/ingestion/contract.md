# ingestion

- Feature: Data ingestion
- Status: **implemented**
- Implementation: `assistant/rag/ingest.py + scripts/build_corpus.py + scripts/build_vault.py`
- Model tier: offline
- Tool allowlist: none

## Purpose
Chunk docs, build index, vault notes and graph.

## Non-goals / guardrails
Versioned output; no signing yet.

## Required before 'done'
I/O schemas, timeouts, FMEA rows, OTel spans, eval set, owner.
