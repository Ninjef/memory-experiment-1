"""Pluggable clusterer modules for grouping embedded chunks."""

import importlib


def load_clusterer_module(name: str):
    """Load a clusterer module by name from src.clusterers.<name>."""
    return importlib.import_module(f"src.clusterers.{name}")
