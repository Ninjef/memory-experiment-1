# CHUNKING_AND_NOMIC — Gemini Chat Chunking + Embedding Model Upgrade — 2026-04-08

## What was built

A chunking script for Gemini chat data and an upgrade from all-MiniLM-L6-v2 to nomic-embed-text-v1.5 as the default embedding model.

---

## Problem

The extracted Gemini chat JSON (from GEMINI_PARSER) contained 1,439 raw entries but had no chunking logic to convert them into pipeline-ready JSONL. Additionally, the existing embedding model (all-MiniLM-L6-v2) had a 256-token max sequence length, meaning most conversation entries were silently truncated during embedding — the median AI response alone was ~2,654 chars (~660 tokens).

## Solution

### 1. Embedding model switch: nomic-embed-text-v1.5

Replaced all-MiniLM-L6-v2 (384-dim, 256 tokens) with nomic-embed-text-v1.5 (768-dim, 8,192 tokens). This provides higher quality embeddings (MTEB ~62 vs ~56) and a 32x larger context window, drastically reducing the need for aggressive chunking.

**Key implementation details:**
- nomic requires a `search_document: ` prefix on all input texts. This is handled transparently in the embedder — callers never see the prefix, but it's included in cache keys.
- `trust_remote_code=True` is needed for nomic's custom architecture.
- Added `einops` dependency (required by nomic at runtime).
- Added `--embedding-model` CLI flag to `run.py` for per-run overrides.

### 2. Chunking script: `scripts/chunk_gemini_chats.py`

Standalone CLI script that reads `gemini_chats.json` and outputs JSONL.

**Chunking strategy:**
- Short conversations (combined user prompt + AI response <= 5,000 chars): kept as a single chunk
- Long conversations: AI response split on paragraph boundaries with 1-paragraph overlap; user prompt inlined in first chunk, stored in metadata for subsequent chunks
- Oversized user prompts (e.g. resume dumps): truncated inline, full text preserved in metadata
- Canvas entries supported via `canvas_title` as context prefix

**Modes:**
- Default: full conversation chunks (user prompt + AI response)
- `--user-prompts-only`: exports only the user's messages — useful for lightweight experimentation

**Stats (default mode):** 1,439 entries -> 2,232 chunks, all within 5,000 char limit
**Stats (user-prompts-only):** 1,328 chunks, median 218 chars

### Files changed

- **`scripts/chunk_gemini_chats.py`** — New chunking script
- **`src/embedder.py`** — Default model changed to nomic, added prefix logic and trust_remote_code
- **`run.py`** — Added `--embedding-model` CLI flag, fixed hardcoded model name in metadata
- **`requirements.txt`** — Added `einops>=0.7.0`
- **`tests/test_embedder_cache.py`** — Updated to use `DEFAULT_MODEL_NAME` and handle prefixed cache keys

### Verification

- All 67 tests pass
- End-to-end pipeline tested: chunking -> nomic embedding -> UMAP -> HDBSCAN clustering produces valid output
- Both chunking modes (full conversation and user-prompts-only) verified
