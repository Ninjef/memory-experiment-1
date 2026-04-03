"""Pluggable prompt modules for insight generation."""

from __future__ import annotations

import importlib
from typing import Protocol


class PromptModule(Protocol):
    """Contract for prompt modules used by the synthesizer."""

    def system_prompt(self) -> str:
        """Return the system prompt text to send to the LLM."""
        ...

    def parse_response(self, raw_json: object) -> list[dict]:
        """Parse the LLM's JSON response into a list of insight dicts.

        Each dict must have an 'insight' key (str) containing the insight text.
        Additional keys (confidence, suggestedAction, etc.) are preserved as
        metadata. The raw_json may be a dict or list depending on what the
        prompt asked the LLM to return.
        """
        ...


def load_prompt(name: str) -> PromptModule:
    """Load and instantiate a prompt module by name from src.prompts.<name>.

    The module must define a class named ``Prompt`` that satisfies the
    ``PromptModule`` protocol.
    """
    module = importlib.import_module(f"src.prompts.{name}")
    return module.Prompt()
