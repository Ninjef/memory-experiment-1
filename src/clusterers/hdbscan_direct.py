"""Direct HDBSCAN clustering: runs HDBSCAN on the full-dimensional embeddings
without any UMAP dimensionality reduction beforehand.

This can be useful when you want clustering to operate on the original embedding
space rather than a compressed representation, preserving all signal at the cost
of higher compute on large datasets.
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


class HDBSCANDirectClusterer:
    """Clusters full-dimensional embeddings directly with HDBSCAN (no UMAP)."""

    def __init__(
        self,
        min_cluster_size: int = 3,
        min_samples: int | None = None,
    ) -> None:
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        if len(chunks) < self.min_cluster_size:
            return {0: chunks}

        embeddings = np.array([c.embedding for c in chunks])

        log.info(
            "Running HDBSCAN directly on %d-dim embeddings (min_cluster_size=%d)...",
            embeddings.shape[1],
            self.min_cluster_size,
        )
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
        )
        labels = clusterer.fit_predict(embeddings)

        groups: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk, label in zip(chunks, labels):
            groups[int(label)].append(chunk)

        if list(groups.keys()) == [-1]:
            log.info("All chunks classified as noise — grouping into one cluster.")
            return {0: chunks}

        noise_count = len(groups.get(-1, []))
        real_clusters = {k: v for k, v in groups.items() if k != -1}
        log.info(
            "HDBSCAN complete: %d cluster(s), %d noise points.",
            len(real_clusters),
            noise_count,
        )
        for cid, members in real_clusters.items():
            log.debug("  Cluster %d: %d chunks", cid, len(members))

        return dict(groups)

    def reduce_for_viz(
        self, chunks: list[MemoryChunk], n_components: int = 3
    ) -> np.ndarray:
        """Run UMAP reduction for visualization only."""
        embeddings = np.array([c.embedding for c in chunks])
        n_neighbors = min(15, len(chunks) - 1)
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
    """Register HDBSCAN-direct CLI arguments."""
    group = parser.add_argument_group("hdbscan_direct clusterer")
    group.add_argument(
        "--min-cluster-size",
        type=int,
        default=3,
        help="Minimum cluster size for HDBSCAN (default: 3)",
    )


def create(args: argparse.Namespace, embedder) -> HDBSCANDirectClusterer:
    """Build an HDBSCANDirectClusterer from parsed CLI args."""
    return HDBSCANDirectClusterer(min_cluster_size=args.min_cluster_size)
