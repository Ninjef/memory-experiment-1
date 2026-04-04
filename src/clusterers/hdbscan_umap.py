"""HDBSCAN-then-UMAP clustering: clusters on the full-dimensional embeddings
first, then applies UMAP reduction afterward.

This reverses the default pipeline's order. HDBSCAN sees the original embedding
space (preserving all signal for cluster assignment), while UMAP is used only
for downstream visualization and dimensionality reduction after clusters are
already determined.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict

import hdbscan
import numpy as np
import umap

from src.models import MemoryChunk

log = logging.getLogger(__name__)


class HDBSCANUMAPClusterer:
    """Clusters full-dimensional embeddings with HDBSCAN, then reduces with UMAP."""

    def __init__(
        self,
        min_cluster_size: int = 3,
        min_samples: int | None = None,
        umap_n_components: int = 10,
        umap_n_neighbors: int = 15,
        umap_min_dist: float = 0.0,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.umap_n_components = umap_n_components
        self.umap_n_neighbors = umap_n_neighbors
        self.umap_min_dist = umap_min_dist

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        if len(chunks) < self.min_cluster_size:
            return {0: chunks}

        embeddings = np.array([c.embedding for c in chunks])

        # Step 1: Cluster on full-dimensional embeddings
        log.info(
            "Running HDBSCAN on %d-dim embeddings (min_cluster_size=%d)...",
            embeddings.shape[1],
            self.min_cluster_size,
        )
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
        )
        labels = clusterer.fit_predict(embeddings)

        # Step 2: Reduce embeddings with UMAP (post-clustering)
        n_components = min(self.umap_n_components, len(chunks) - 1)
        n_neighbors = min(self.umap_n_neighbors, len(chunks) - 1)

        log.info(
            "Running post-cluster UMAP reduction (%d -> %d dims)...",
            embeddings.shape[1],
            n_components,
        )
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=self.umap_min_dist,
            random_state=42,
        )
        reduced = reducer.fit_transform(embeddings)

        # Replace chunk embeddings with UMAP-reduced versions
        for chunk, emb in zip(chunks, reduced):
            chunk.embedding = emb.tolist()

        groups: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk, label in zip(chunks, labels):
            groups[int(label)].append(chunk)

        if list(groups.keys()) == [-1]:
            log.info("All chunks classified as noise — grouping into one cluster.")
            return {0: chunks}

        noise_count = len(groups.get(-1, []))
        real_clusters = {k: v for k, v in groups.items() if k != -1}
        log.info(
            "HDBSCAN complete: %d cluster(s), %d noise points. Embeddings reduced to %d dims.",
            len(real_clusters),
            noise_count,
            n_components,
        )
        for cid, members in real_clusters.items():
            log.debug("  Cluster %d: %d chunks", cid, len(members))

        return dict(groups)

    def reduce_for_viz(
        self, chunks: list[MemoryChunk], n_components: int = 3
    ) -> np.ndarray:
        """Run UMAP reduction for visualization."""
        embeddings = np.array([c.embedding for c in chunks])
        n_neighbors = min(self.umap_n_neighbors, len(chunks) - 1)
        n_components = min(n_components, len(chunks) - 1)

        log.info(
            "Running UMAP for visualization (%d -> %d dims)...",
            embeddings.shape[1],
            n_components,
        )
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            random_state=42,
        )
        return reducer.fit_transform(embeddings)


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register HDBSCAN-then-UMAP CLI arguments."""
    group = parser.add_argument_group("hdbscan_umap clusterer")
    group.add_argument(
        "--min-cluster-size",
        type=int,
        default=3,
        help="Minimum cluster size for HDBSCAN (default: 3)",
    )


def create(args: argparse.Namespace, embedder) -> HDBSCANUMAPClusterer:
    """Build an HDBSCANUMAPClusterer from parsed CLI args."""
    return HDBSCANUMAPClusterer(min_cluster_size=args.min_cluster_size)
