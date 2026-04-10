"""Random cluster assignment: divides chunks into ~N/15 clusters by randomly
assigning each chunk to a cluster with Dirichlet-weighted probabilities.

This produces clusters of varying sizes without any single cluster dominating.
Useful for generating baseline comparisons or testing visualization tools.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict

import numpy as np
import umap

from src.models import MemoryChunk

log = logging.getLogger(__name__)


class RandomAssignClusterer:
    """Randomly assigns chunks to clusters with weighted probabilities."""

    def __init__(
        self,
        chunks_per_cluster: int = 15,
        dirichlet_alpha: float = 2.0,
        seed: int | None = None,
    ) -> None:
        self.chunks_per_cluster = chunks_per_cluster
        self.dirichlet_alpha = dirichlet_alpha
        self.seed = seed

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        n = len(chunks)
        if n == 0:
            return {0: []}

        num_clusters = max(1, n // self.chunks_per_cluster)
        rng = np.random.default_rng(self.seed)

        # Dirichlet distribution gives varied but bounded cluster weights.
        # Alpha=2.0 keeps things spread out enough that no single cluster
        # is likely to grab >70% of points, while still allowing good variance.
        weights = rng.dirichlet(
            np.full(num_clusters, self.dirichlet_alpha)
        )
        labels = rng.choice(num_clusters, size=n, p=weights)

        groups: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk, label in zip(chunks, labels):
            groups[int(label)].append(chunk)

        log.info(
            "Random assignment: %d chunks -> %d clusters (target ~%d per cluster)",
            n, len(groups), self.chunks_per_cluster,
        )
        for cid in sorted(groups):
            log.debug("  Cluster %d: %d chunks", cid, len(groups[cid]))

        return dict(groups)

    def reduce_for_viz(
        self, chunks: list[MemoryChunk], n_components: int = 3
    ) -> np.ndarray:
        """Run UMAP reduction for 3D visualization coordinates."""
        embeddings = np.array([c.embedding for c in chunks])
        n_neighbors = min(15, len(chunks) - 1)
        n_components = min(n_components, len(chunks) - 1)

        log.info(
            "Running UMAP for visualization (%d -> %d dims)...",
            embeddings.shape[1], n_components,
        )
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            random_state=42,
        )
        return reducer.fit_transform(embeddings)


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register random-assign-specific CLI arguments."""
    group = parser.add_argument_group("random_assign clusterer")
    group.add_argument(
        "--chunks-per-cluster",
        type=int,
        default=15,
        help="Target chunks per cluster; num_clusters = N / this value (default: 15)",
    )
    group.add_argument(
        "--dirichlet-alpha",
        type=float,
        default=2.0,
        help="Dirichlet concentration parameter — lower = more variance (default: 2.0)",
    )
    group.add_argument(
        "--random-seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: None)",
    )


def create(args: argparse.Namespace, embedder) -> RandomAssignClusterer:
    """Build a RandomAssignClusterer from parsed CLI args."""
    return RandomAssignClusterer(
        chunks_per_cluster=args.chunks_per_cluster,
        dirichlet_alpha=args.dirichlet_alpha,
        seed=args.random_seed,
    )
