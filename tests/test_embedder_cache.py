"""Tests for SentenceTransformerEmbedder with caching integration."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.embedding_cache import EmbeddingCache
from src.embedder import DEFAULT_MODEL_NAME, _MODEL_PREFIXES, SentenceTransformerEmbedder
from src.models import MemoryChunk

_PREFIX = _MODEL_PREFIXES.get(DEFAULT_MODEL_NAME, "")


def _fake_encode(texts, show_progress_bar=False):
    """Return deterministic fake embeddings (3-dim for speed)."""
    return np.array([[float(hash(t) % 100)] * 3 for t in texts], dtype=np.float32)


@pytest.fixture
def mock_st():
    """Patch SentenceTransformer so the real model is never loaded."""
    with patch("sentence_transformers.SentenceTransformer") as MockST:
        instance = MagicMock()
        instance.encode = _fake_encode
        MockST.return_value = instance
        yield MockST


def test_uncached_texts_trigger_model_load(tmp_path, mock_st):
    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    chunks = [MemoryChunk(text="hello"), MemoryChunk(text="world")]
    embedder.embed(chunks)

    mock_st.assert_called_once()  # Model was loaded
    assert chunks[0].embedding is not None
    assert chunks[1].embedding is not None


def test_cached_texts_skip_model_load(tmp_path, mock_st):
    # Pre-populate cache with prefixed keys (as the embedder stores them)
    cache = EmbeddingCache(tmp_path, DEFAULT_MODEL_NAME)
    cache.put_many({
        f"{_PREFIX}hello": [1.0, 2.0, 3.0],
        f"{_PREFIX}world": [4.0, 5.0, 6.0],
    })
    cache.close()

    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    chunks = [MemoryChunk(text="hello"), MemoryChunk(text="world")]
    embedder.embed(chunks)

    mock_st.assert_not_called()  # Model never loaded
    assert chunks[0].embedding == [1.0, 2.0, 3.0]
    assert chunks[1].embedding == [4.0, 5.0, 6.0]


def test_partial_cache_only_encodes_uncached(tmp_path, mock_st):
    # Cache one text with prefixed key
    cache = EmbeddingCache(tmp_path, DEFAULT_MODEL_NAME)
    cache.put_many({f"{_PREFIX}cached text": [1.0, 2.0, 3.0]})
    cache.close()

    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    chunks = [
        MemoryChunk(text="cached text"),
        MemoryChunk(text="new text"),
        MemoryChunk(text="another new"),
    ]
    embedder.embed(chunks)

    mock_st.assert_called_once()  # Model loaded for uncached texts
    assert chunks[0].embedding == [1.0, 2.0, 3.0]  # From cache
    assert chunks[1].embedding is not None  # From model
    assert chunks[2].embedding is not None  # From model


def test_no_cache_flag_bypasses_cache(tmp_path, mock_st):
    # Pre-populate cache with prefixed key
    cache = EmbeddingCache(tmp_path, DEFAULT_MODEL_NAME)
    cache.put_many({f"{_PREFIX}hello": [1.0, 2.0, 3.0]})
    cache.close()

    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path, no_cache=True)
    chunks = [MemoryChunk(text="hello")]
    embedder.embed(chunks)

    mock_st.assert_called_once()  # Model loaded despite cache existing
    # Embedding comes from model, not cache
    assert chunks[0].embedding != [1.0, 2.0, 3.0]


def test_new_embeddings_are_persisted(tmp_path, mock_st):
    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    chunks = [MemoryChunk(text="persist me")]
    embedder.embed(chunks)
    original_embedding = chunks[0].embedding

    # Verify it's in the cache via a fresh cache instance (using prefixed key)
    cache = EmbeddingCache(tmp_path, DEFAULT_MODEL_NAME)
    result = cache.get_many([f"{_PREFIX}persist me"])
    assert f"{_PREFIX}persist me" in result
    np.testing.assert_array_almost_equal(result[f"{_PREFIX}persist me"], original_embedding, decimal=6)
    cache.close()


def test_empty_chunks_returns_empty(tmp_path, mock_st):
    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    result = embedder.embed([])
    assert result == []
    mock_st.assert_not_called()


def test_duplicate_texts_in_batch(tmp_path, mock_st):
    embedder = SentenceTransformerEmbedder(cache_dir=tmp_path)
    chunks = [MemoryChunk(text="same"), MemoryChunk(text="same")]
    embedder.embed(chunks)
    assert chunks[0].embedding == chunks[1].embedding
