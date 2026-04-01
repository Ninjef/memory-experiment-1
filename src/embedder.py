from __future__ import annotations

import logging

from sentence_transformers import SentenceTransformer

from src.models import MemoryChunk

log = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, ~80MB, fast


class SentenceTransformerEmbedder:
    """Embeds chunks using a local sentence-transformer model."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        log.info("Loading embedding model '%s' (may download on first run)...", model_name)
        self.model = SentenceTransformer(model_name)
        log.info("Embedding model loaded.")

    def embed(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        log.info("Embedding %d chunks...", len(chunks))
        texts = [c.text for c in chunks]
        embeddings = self.model.encode(texts, show_progress_bar=True)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb.tolist()
        log.info("Embedding complete (dim=%d).", len(chunks[0].embedding))
        return chunks
