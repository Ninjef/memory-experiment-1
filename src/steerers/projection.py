"""Projection-based steering: amplify the component of each memory embedding
that aligns with dream-director theme vectors.

Math per theme t and memory embedding m:
    proj     = (m . t / t . t) * t      # component of m along t
    steered  = m + (alpha - 1) * proj   # amplify that component
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from src.models import MemoryChunk

log = logging.getLogger(__name__)


class ProjectionSteerer:
    """Amplifies theme-aligned components of memory embeddings."""

    def __init__(self, theme_embeddings: np.ndarray, alpha: float = 2.0) -> None:
        self.theme_embeddings = theme_embeddings  # (n_themes, embed_dim)
        self.alpha = alpha

    def steer(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        factor = self.alpha - 1.0
        for chunk in chunks:
            v = np.array(chunk.embedding, dtype=np.float64)
            for theme in self.theme_embeddings:
                denom = np.dot(theme, theme)
                if denom < 1e-12:
                    continue
                proj = (np.dot(v, theme) / denom) * theme
                v = v + factor * proj
            chunk.embedding = v.tolist()
        return chunks


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register projection-steerer CLI arguments."""
    group = parser.add_argument_group("projection steerer")
    group.add_argument(
        "--themes-file",
        default=None,
        help="Path to newline-delimited file of theme strings",
    )
    group.add_argument(
        "--themes",
        nargs="+",
        default=None,
        help='Theme strings (inline), e.g. --themes "financial anxieties" "food and budget"',
    )
    group.add_argument(
        "--steer-alpha",
        type=float,
        default=2.0,
        help="Amplification factor for theme components (default: 2.0)",
    )


def create(args: argparse.Namespace, embedder) -> ProjectionSteerer:
    """Build a ProjectionSteerer from parsed CLI args."""
    # Resolve theme strings
    if args.themes_file:
        themes = Path(args.themes_file).read_text().strip().splitlines()
        themes = [t.strip() for t in themes if t.strip()]
    elif args.themes:
        themes = args.themes
    else:
        raise ValueError(
            "Projection steerer requires --themes-file or --themes"
        )

    if not themes:
        raise ValueError("No themes provided")

    log.info("Embedding %d theme(s): %s", len(themes), themes)

    # Embed themes using the same model as memory chunks
    theme_chunks = [MemoryChunk(text=t) for t in themes]
    theme_chunks = embedder.embed(theme_chunks)
    theme_embeddings = np.array([c.embedding for c in theme_chunks])

    return ProjectionSteerer(
        theme_embeddings=theme_embeddings,
        alpha=args.steer_alpha,
    )
