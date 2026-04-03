"""Default insight prompt — generates 1-3 insights per cluster as a JSON array."""

from __future__ import annotations


class Prompt:
    """Original synthesizer prompt preserved for backward compatibility."""

    def system_prompt(self) -> str:
        return (
            "You are analyzing a set of related memories or text snippets from a user. "
            "Your job is to identify higher-level insights, patterns, or reflections that "
            "connect these memories. Each insight should reveal something not obvious from "
            "any single memory alone.\n\n"
            "Respond with a JSON array of objects, each with a single 'text' field containing "
            "one insight. Return 1-3 insights depending on how much can be meaningfully inferred. "
            "Respond ONLY with the raw JSON array — no markdown, no code fences, no commentary."
        )

    def parse_response(self, raw_json: object) -> list[dict]:
        if not isinstance(raw_json, list):
            raw_json = [raw_json]
        return [{"insight": item.get("text", str(item))} for item in raw_json]
