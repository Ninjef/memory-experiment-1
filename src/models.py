from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class MemoryChunk:
    """Universal data unit for the memory processing pipeline.

    `text` is required. Everything else is flexible:
    - `metadata` holds arbitrary key-value pairs (timestamps, source, tags, etc.)
    - `embedding` is populated by the Embedder stage and stripped on serialization
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    embedding: list[float] | None = None

    def to_dict(self, include_embedding: bool = False) -> dict[str, Any]:
        """Serialize to a flat dict suitable for JSONL output."""
        d: dict[str, Any] = {"id": self.id, "text": self.text, **self.metadata}
        if include_embedding and self.embedding is not None:
            d["embedding"] = self.embedding
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryChunk:
        """Construct from a flat dict (one JSONL line)."""
        text = data.pop("text")
        chunk_id = data.pop("id", None) or str(uuid4())
        embedding = data.pop("embedding", None)
        return cls(text=text, metadata=data, id=chunk_id, embedding=embedding)
