"""SQLite-backed embedding cache.

Stores embeddings keyed by (model_name, text) so repeated runs with the
same input skip model loading and re-computation entirely.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = ".cache"
_DB_FILENAME = "embeddings.db"


def _cache_key(model_name: str, text: str) -> str:
    """SHA-256 of model_name + null byte + text."""
    return hashlib.sha256(f"{model_name}\0{text}".encode()).hexdigest()


class EmbeddingCache:
    """Persistent embedding cache backed by a SQLite database."""

    def __init__(self, cache_dir: str | Path, model_name: str) -> None:
        self.model_name = model_name
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        db_path = cache_path / _DB_FILENAME
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key  TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                text       TEXT NOT NULL,
                embedding  BLOB NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_many(self, texts: list[str]) -> dict[str, list[float]]:
        """Look up cached embeddings for a batch of texts.

        Returns a dict mapping text -> embedding list for cache hits only.
        """
        if not texts:
            return {}

        keys = {_cache_key(self.model_name, t): t for t in texts}
        placeholders = ",".join("?" for _ in keys)
        cursor = self._conn.execute(
            f"SELECT cache_key, embedding FROM embeddings WHERE cache_key IN ({placeholders})",
            list(keys.keys()),
        )

        result: dict[str, list[float]] = {}
        for row in cursor:
            key, blob = row
            text = keys[key]
            embedding = np.frombuffer(blob, dtype=np.float32).tolist()
            result[text] = embedding
        return result

    def put_many(self, entries: dict[str, list[float]]) -> None:
        """Store a batch of text -> embedding pairs in the cache."""
        if not entries:
            return

        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for text, embedding in entries.items():
            key = _cache_key(self.model_name, text)
            blob = np.array(embedding, dtype=np.float32).tobytes()
            rows.append((key, self.model_name, text, blob, now))

        self._conn.executemany(
            "INSERT OR REPLACE INTO embeddings (cache_key, model_name, text, embedding, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._conn.execute("DELETE FROM embeddings")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
