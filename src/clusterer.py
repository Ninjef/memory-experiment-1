from __future__ import annotations

import logging
from collections import defaultdict

import hdbscan
import numpy as np
import umap

from src.models import MemoryChunk

log = logging.getLogger(__name__)


class UMAPHDBSCANClusterer:
    """Reduces dimensionality with UMAP, then clusters with HDBSCAN."""

    def __init__(
        self,
        umap_n_components: int = 10,
        umap_n_neighbors: int = 15,
        umap_min_dist: float = 0.0,
        hdbscan_min_cluster_size: int = 3,
        hdbscan_min_samples: int | None = None,
    ) -> None:
        self.umap_n_components = umap_n_components
        self.umap_n_neighbors = umap_n_neighbors
        self.umap_min_dist = umap_min_dist
        self.hdbscan_min_cluster_size = hdbscan_min_cluster_size
        self.hdbscan_min_samples = hdbscan_min_samples

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        if len(chunks) < self.hdbscan_min_cluster_size:
            # Too few chunks to cluster meaningfully — return all as one group
            return {0: chunks}

        embeddings = np.array([c.embedding for c in chunks])

        # Adjust UMAP components if we have fewer samples than requested dims
        n_components = min(self.umap_n_components, len(chunks) - 1)
        n_neighbors = min(self.umap_n_neighbors, len(chunks) - 1)

        log.info("Running UMAP reduction (%d -> %d dims, %d neighbors)...", embeddings.shape[1], n_components, n_neighbors)
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=self.umap_min_dist,
            random_state=42,
        )
        reduced = reducer.fit_transform(embeddings)
        log.info("UMAP complete.")

        log.info("Running HDBSCAN (min_cluster_size=%d)...", self.hdbscan_min_cluster_size)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.hdbscan_min_cluster_size,
            min_samples=self.hdbscan_min_samples,
        )
        labels = clusterer.fit_predict(reduced)

        groups: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk, label in zip(chunks, labels):
            groups[int(label)].append(chunk)

        # If everything ended up as noise (-1), put them all in one cluster
        if list(groups.keys()) == [-1]:
            log.info("All chunks classified as noise — grouping into one cluster.")
            return {0: chunks}

        noise_count = len(groups.get(-1, []))
        real_clusters = {k: v for k, v in groups.items() if k != -1}
        log.info("HDBSCAN complete: %d cluster(s), %d noise points.", len(real_clusters), noise_count)
        for cid, members in real_clusters.items():
            log.debug("  Cluster %d: %d chunks", cid, len(members))

        return dict(groups)

    def reduce_for_viz(
        self, chunks: list[MemoryChunk], n_components: int = 3
    ) -> np.ndarray:
        """Run a separate UMAP reduction to low-dimensional coords for visualization."""
        embeddings = np.array([c.embedding for c in chunks])
        n_neighbors = min(self.umap_n_neighbors, len(chunks) - 1)
        n_components = min(n_components, len(chunks) - 1)

        log.info("Running UMAP for visualization (%d -> %d dims)...", embeddings.shape[1], n_components)
        reducer = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            random_state=42,
        )
        return reducer.fit_transform(embeddings)
