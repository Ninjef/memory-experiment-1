"""Theme-based nearest-neighbor clustering: assigns each chunk to the theme
it is most similar to (by cosine similarity), forming one cluster per theme.

This is an alternative to the UMAP+HDBSCAN approach — instead of discovering
clusters in the embedding space, we define clusters by proximity to known
theme vectors.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import umap

from src.models import MemoryChunk

log = logging.getLogger(__name__)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between matrix a (n, d) and vector b (d,)."""
    norm_a = np.linalg.norm(a, axis=1, keepdims=True)
    norm_b = np.linalg.norm(b)
    if norm_b < 1e-12:
        return np.zeros(a.shape[0])
    return (a @ b) / (norm_a.squeeze() * norm_b)


class ThemeNearestNeighborClusterer:
    """Clusters chunks by cosine similarity to theme embeddings."""

    def __init__(
        self,
        theme_embeddings: np.ndarray,
        theme_labels: list[str],
        top_k: int | None = None,
        threshold: float = 0.3,
    ) -> None:
        self.theme_embeddings = theme_embeddings  # (n_themes, embed_dim)
        self.theme_labels = theme_labels
        self.top_k = top_k
        self.threshold = threshold

    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        if not chunks:
            return {}

        embeddings = np.array([c.embedding for c in chunks])
        n_themes = len(self.theme_embeddings)

        # Compute cosine similarity of each chunk to each theme: (n_chunks, n_themes)
        similarities = np.column_stack(
            [_cosine_similarity(embeddings, theme) for theme in self.theme_embeddings]
        )

        log.info(
            "Computing cosine similarities for %d chunks against %d theme(s)...",
            len(chunks),
            n_themes,
        )

        # For each chunk, find its best theme and the similarity score
        best_theme = np.argmax(similarities, axis=1)
        best_score = np.max(similarities, axis=1)

        # Assign chunks: must meet threshold, and optionally respect top_k per theme
        groups: dict[int, list[tuple[float, MemoryChunk]]] = defaultdict(list)
        noise: list[MemoryChunk] = []

        for i, chunk in enumerate(chunks):
            theme_id = int(best_theme[i])
            score = float(best_score[i])
            if score >= self.threshold:
                groups[theme_id].append((score, chunk))
            else:
                noise.append(chunk)

        # Apply top_k limit per theme if set
        if self.top_k is not None:
            for theme_id in list(groups.keys()):
                members = sorted(groups[theme_id], key=lambda x: x[0], reverse=True)
                overflow = members[self.top_k :]
                groups[theme_id] = members[: self.top_k]
                noise.extend(chunk for _, chunk in overflow)

        # Build final result
        result: dict[int, list[MemoryChunk]] = {}
        for theme_id, scored_members in groups.items():
            members = [chunk for _, chunk in scored_members]
            result[theme_id] = members
            log.info(
                "  Theme %d (%s): %d chunks",
                theme_id,
                self.theme_labels[theme_id],
                len(members),
            )

        if noise:
            result[-1] = noise
            log.info("  Noise: %d chunks below threshold %.2f", len(noise), self.threshold)

        # If nothing passed the threshold, put everything in one cluster
        if not any(k >= 0 for k in result):
            log.info("No chunks met threshold — grouping all into one cluster.")
            return {0: chunks}

        return result

    def reduce_for_viz(
        self, chunks: list[MemoryChunk], n_components: int = 3
    ) -> np.ndarray:
        """Run UMAP reduction for visualization (same as umap_hdbscan)."""
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
    """Register theme nearest-neighbor clusterer CLI arguments."""
    group = parser.add_argument_group("theme nearest-neighbor clusterer")
    group.add_argument(
        "--cluster-themes-file",
        default=None,
        help="Path to newline-delimited file of theme strings for clustering",
    )
    group.add_argument(
        "--cluster-themes",
        nargs="+",
        default=None,
        help='Theme strings for clustering (inline), e.g. --cluster-themes "financial anxieties" "food and budget"',
    )
    group.add_argument(
        "--theme-top-k",
        type=int,
        default=None,
        help="Maximum number of nearest neighbors per theme (default: unlimited)",
    )
    group.add_argument(
        "--theme-threshold",
        type=float,
        default=0.3,
        help="Minimum cosine similarity to assign a chunk to a theme (default: 0.3)",
    )


def create(args: argparse.Namespace, embedder) -> ThemeNearestNeighborClusterer:
    """Build a ThemeNearestNeighborClusterer from parsed CLI args."""
    # Resolve theme strings
    if args.cluster_themes_file:
        themes = Path(args.cluster_themes_file).read_text().strip().splitlines()
        themes = [t.strip() for t in themes if t.strip()]
    elif args.cluster_themes:
        themes = args.cluster_themes
    else:
        raise ValueError(
            "Theme nearest-neighbor clusterer requires --cluster-themes-file or --cluster-themes"
        )

    if not themes:
        raise ValueError("No cluster themes provided")

    log.info("Embedding %d cluster theme(s): %s", len(themes), themes)

    # Embed themes using the same model as memory chunks
    theme_chunks = [MemoryChunk(text=t) for t in themes]
    theme_chunks = embedder.embed(theme_chunks)
    theme_embeddings = np.array([c.embedding for c in theme_chunks])

    return ThemeNearestNeighborClusterer(
        theme_embeddings=theme_embeddings,
        theme_labels=themes,
        top_k=args.theme_top_k,
        threshold=args.theme_threshold,
    )
