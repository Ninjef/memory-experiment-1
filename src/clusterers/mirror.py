"""Mirror clusterer: copies cluster assignments from a previous run's output.

Reads clusters.json from a base run directory and assigns chunks to the same
cluster IDs by matching on chunk text (with ID as a fallback). Useful for
comparing visualizations across runs (e.g., before/after steering) with
consistent cluster colors.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import umap

from src.models import MemoryChunk

log = logging.getLogger(__name__)


class MirrorClusterer:
    """Assigns chunks to clusters by mirroring a previous run's assignments."""

    def __init__(self, base_dir: Path) -> None:
        clusters_path = base_dir / "clusters.json"
        with open(clusters_path, encoding="utf-8") as f:
            clusters_data = json.load(f)

        self._text_to_cluster: dict[str, int] = {}
        self._id_to_cluster: dict[str, int] = {}
        for entry in clusters_data:
            cluster_id = entry["cluster_id"]
            for member in entry["members"]:
                self._id_to_cluster[member["id"]] = cluster_id
                self._text_to_cluster[member["text"]] = cluster_id

        log.info(
            "Loaded %d chunk-to-cluster mappings from %s",
            len(self._id_to_cluster),
            clusters_path,
        )

    def _lookup(self, chunk: MemoryChunk) -> int | None:
        """Look up cluster ID by chunk ID first, then by text."""
        if chunk.id in self._id_to_cluster:
            return self._id_to_cluster[chunk.id]
        if chunk.text in self._text_to_cluster:
            return self._text_to_cluster[chunk.text]
        return None

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        matched = 0
        unmatched = 0
        groups: dict[int, list[MemoryChunk]] = defaultdict(list)
        for chunk in chunks:
            cluster_id = self._lookup(chunk)
            if cluster_id is not None:
                groups[cluster_id].append(chunk)
                matched += 1
            else:
                groups[-1].append(chunk)
                unmatched += 1

        if unmatched:
            log.warning(
                "%d chunk(s) in current run not found in base run (assigned to noise cluster -1)",
                unmatched,
            )
        if matched == 0:
            log.error(
                "No chunks matched between base and current run — "
                "all assigned to noise. Is --mirror-base-dir correct?"
            )
        else:
            log.info("Matched %d / %d chunks to base clusters", matched, len(chunks))

        for cid in sorted(groups):
            label = "noise" if cid == -1 else f"cluster_{cid}"
            log.info("  %s: %d chunks", label, len(groups[cid]))

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
    """Register mirror-specific CLI arguments."""
    group = parser.add_argument_group("mirror clusterer")
    group.add_argument(
        "--mirror-base-dir",
        type=str,
        default=None,
        help="Path to a previous run's output directory containing clusters.json",
    )


def create(args: argparse.Namespace, embedder) -> MirrorClusterer:
    """Build a MirrorClusterer from parsed CLI args."""
    if not args.mirror_base_dir:
        print("error: --mirror-base-dir is required when using --clusterer mirror", file=sys.stderr)
        sys.exit(1)

    base_dir = Path(args.mirror_base_dir)
    clusters_path = base_dir / "clusters.json"
    if not clusters_path.exists():
        print(f"error: {clusters_path} not found", file=sys.stderr)
        sys.exit(1)

    return MirrorClusterer(base_dir)
