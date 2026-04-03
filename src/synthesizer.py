from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from src.models import MemoryChunk
from src.prompts import PromptModule

log = logging.getLogger(__name__)

# Latest Anthropic model names (swap as needed):
#   opus:   claude-opus-4-6
#   sonnet: claude-sonnet-4-6
#   haiku:  claude-haiku-4-5-20251001
DEFAULT_MODEL = "claude-sonnet-4-6"


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) if present."""
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


class AnthropicSynthesizer:
    """Generates insights from memory clusters using the Anthropic API."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        prompt_module: PromptModule | None = None,
    ) -> None:
        self.model = model
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

        if prompt_module is None:
            from src.prompts.default import Prompt
            prompt_module = Prompt()
        self.prompt_module = prompt_module

    def synthesize(
        self, clusters: dict[int, list[MemoryChunk]]
    ) -> list[MemoryChunk]:
        all_insights: list[MemoryChunk] = []

        eligible = {k: v for k, v in clusters.items() if k != -1 and len(v) >= 2}
        log.info("Synthesizing %d cluster(s) (skipping noise and single-member clusters)...", len(eligible))

        for i, (cluster_id, chunks) in enumerate(eligible.items(), 1):
            log.info("  [%d/%d] Cluster %d (%d chunks) — calling %s...", i, len(eligible), cluster_id, len(chunks), self.model)
            insights = self._synthesize_cluster(cluster_id, chunks)
            log.info("  [%d/%d] Got %d insight(s).", i, len(eligible), len(insights))
            all_insights.extend(insights)

        log.info("Synthesis complete: %d total insights.", len(all_insights))
        return all_insights

    def _synthesize_cluster(
        self, cluster_id: int, chunks: list[MemoryChunk]
    ) -> list[MemoryChunk]:
        numbered = "\n".join(
            f"[{i+1}] (id={c.id}) {c.text}" for i, c in enumerate(chunks)
        )
        user_msg = f"Here are {len(chunks)} related memory snippets:\n\n{numbered}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self.prompt_module.system_prompt(),
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text
        source_ids = [c.id for c in chunks]
        source_texts = [c.text for c in chunks]
        now = datetime.now(timezone.utc).isoformat()

        cleaned = _strip_code_fences(raw)
        try:
            raw_json = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning("Failed to parse LLM response as JSON, storing raw text.")
            return [
                MemoryChunk(
                    text=raw,
                    metadata={
                        "type": "insight",
                        "source_ids": source_ids,
                        "source_texts": source_texts,
                        "cluster_id": cluster_id,
                        "generated_at": now,
                        "prompt_result": raw,
                    },
                )
            ]

        parsed_insights = self.prompt_module.parse_response(raw_json)

        insights: list[MemoryChunk] = []
        for parsed in parsed_insights:
            insight_text = parsed.pop("insight")
            metadata: dict[str, Any] = {
                "type": "insight",
                "source_ids": source_ids,
                "source_texts": source_texts,
                "cluster_id": cluster_id,
                "generated_at": now,
                "prompt_result": raw_json,
            }
            # Merge extra fields from prompt (confidence, suggestedAction, etc.)
            metadata.update(parsed)

            insights.append(MemoryChunk(text=insight_text, metadata=metadata))

        return insights
