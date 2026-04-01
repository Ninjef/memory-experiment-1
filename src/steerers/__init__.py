"""Pluggable steerer modules for embedding distortion before clustering."""

import importlib


def load_steerer_module(name: str):
    """Load a steerer module by name from src.steerers.<name>."""
    return importlib.import_module(f"src.steerers.{name}")
