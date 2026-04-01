from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Protocol

from src.models import MemoryChunk


class Embedder(Protocol):
    """Populates the embedding field on each chunk."""

    def embed(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]: ...


class Clusterer(Protocol):
    """Groups embedded chunks into clusters."""

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]: ...


class Steerer(Protocol):
    """Transforms embeddings to amplify specific themes before clustering."""

    def steer(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]: ...


class Synthesizer(Protocol):
    """Generates new insight chunks from clustered memories."""

    def synthesize(self, clusters: dict[int, list[MemoryChunk]]) -> list[MemoryChunk]: ...


@dataclass
class PipelineResult:
    """Everything produced by a pipeline run."""

    insights: list[MemoryChunk]
    clusters: dict[int, list[MemoryChunk]]
    input_chunks: list[MemoryChunk]
    viz_coords: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    viz_coords_original: dict[str, tuple[float, float, float]] = field(default_factory=dict)


class Pipeline:
    """Orchestrates embed → (steer) → cluster → synthesize."""

    def __init__(
        self,
        embedder: Embedder,
        clusterer: Clusterer,
        synthesizer: Synthesizer,
        steerer: Steerer | None = None,
    ) -> None:
        self.embedder = embedder
        self.clusterer = clusterer
        self.synthesizer = synthesizer
        self.steerer = steerer

    def _build_viz_coords(
        self, embedded: list[MemoryChunk], label: str = "steered"
    ) -> dict[str, tuple[float, float, float]]:
        """Compute 3D UMAP coordinates for visualization."""
        if len(embedded) < 3:
            return {}
        print(f"[pipeline] Computing 3D visualization coordinates ({label})...")
        coords_3d = self.clusterer.reduce_for_viz(embedded, n_components=3)
        return {
            chunk.id: (float(coords_3d[i, 0]), float(coords_3d[i, 1]), float(coords_3d[i, 2]))
            for i, chunk in enumerate(embedded)
        }

    def run_cluster_only(self, chunks: list[MemoryChunk]) -> PipelineResult:
        """Run embed → (steer) → cluster only, skipping synthesis."""
        print(f"[pipeline] Embedding {len(chunks)} chunks...")
        embedded = self.embedder.embed(chunks)

        # Snapshot original embeddings before steering mutates them
        original_embedded = None
        if self.steerer is not None:
            original_embedded = copy.deepcopy(embedded)
            print("[pipeline] Steering embeddings...")
            embedded = self.steerer.steer(embedded)

        print("[pipeline] Clustering...")
        clusters = self.clusterer.cluster(embedded)
        print(f"[pipeline] Found {len(clusters)} cluster(s)")

        viz_coords = self._build_viz_coords(embedded)
        viz_coords_original = {}
        if original_embedded is not None:
            viz_coords_original = self._build_viz_coords(
                original_embedded, label="original"
            )

        return PipelineResult(
            insights=[],
            clusters=clusters,
            input_chunks=chunks,
            viz_coords=viz_coords,
            viz_coords_original=viz_coords_original,
        )

    def run(self, chunks: list[MemoryChunk]) -> PipelineResult:
        print(f"[pipeline] Embedding {len(chunks)} chunks...")
        embedded = self.embedder.embed(chunks)

        # Snapshot original embeddings before steering mutates them
        original_embedded = None
        if self.steerer is not None:
            original_embedded = copy.deepcopy(embedded)
            print("[pipeline] Steering embeddings...")
            embedded = self.steerer.steer(embedded)

        print("[pipeline] Clustering...")
        clusters = self.clusterer.cluster(embedded)
        print(f"[pipeline] Found {len(clusters)} cluster(s)")

        print("[pipeline] Synthesizing insights...")
        insights = self.synthesizer.synthesize(clusters)
        print(f"[pipeline] Generated {len(insights)} insight(s)")

        viz_coords = self._build_viz_coords(embedded)
        viz_coords_original = {}
        if original_embedded is not None:
            viz_coords_original = self._build_viz_coords(
                original_embedded, label="original"
            )

        return PipelineResult(
            insights=insights,
            clusters=clusters,
            input_chunks=chunks,
            viz_coords=viz_coords,
            viz_coords_original=viz_coords_original,
        )
