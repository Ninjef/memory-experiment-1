from __future__ import annotations

import logging

from src.embedding_cache import DEFAULT_CACHE_DIR, EmbeddingCache
from src.models import MemoryChunk

log = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"  # 768-dim, ~137MB, 8192 tokens

# Models that require a task prefix prepended to all input texts.
_MODEL_PREFIXES: dict[str, str] = {
    "nomic-ai/nomic-embed-text-v1.5": "search_document: ",
}


class SentenceTransformerEmbedder:
    """Embeds chunks using a local sentence-transformer model.

    Supports on-disk caching so repeated texts skip model loading entirely.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: str | None = DEFAULT_CACHE_DIR,
        no_cache: bool = False,
    ) -> None:
        self.model_name = model_name
        self._model = None  # Loaded on demand
        self._cache = (
            None if no_cache or cache_dir is None
            else EmbeddingCache(cache_dir, model_name)
        )

    def _get_model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("Loading embedding model '%s' (may download on first run)...", self.model_name)
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
            log.info("Embedding model loaded.")
        return self._model

    def embed(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        if not chunks:
            return chunks

        # Apply model-specific prefix (e.g. nomic requires "search_document: ")
        prefix = _MODEL_PREFIXES.get(self.model_name, "")
        texts = [prefix + c.text for c in chunks]

        # Look up cached embeddings
        cached: dict[str, list[float]] = {}
        if self._cache is not None:
            cached = self._cache.get_many(texts)

        uncached_indices = [i for i, t in enumerate(texts) if t not in cached]

        log.info(
            "Embedding %d chunks (%d cached, %d to compute)...",
            len(chunks), len(chunks) - len(uncached_indices), len(uncached_indices),
        )

        # Assign cached embeddings
        for i, text in enumerate(texts):
            if text in cached:
                chunks[i].embedding = cached[text]

        # Compute uncached embeddings (lazy-loads model only if needed)
        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            model = self._get_model()
            new_embeddings = model.encode(uncached_texts, show_progress_bar=True)

            new_entries: dict[str, list[float]] = {}
            for idx, emb in zip(uncached_indices, new_embeddings):
                emb_list = emb.tolist()
                chunks[idx].embedding = emb_list
                new_entries[texts[idx]] = emb_list

            if self._cache is not None:
                self._cache.put_many(new_entries)

        log.info("Embedding complete (dim=%d).", len(chunks[0].embedding))
        return chunks
