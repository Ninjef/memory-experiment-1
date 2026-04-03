# FOURTH_STEP — Insight Generation, Prompt System, Visualization Upgrades

**Date:** 2026-04-03
**Task:** `projectTasks/FOURTH_STEP.md`

## What Was Built

### 1. Pluggable Prompt System (`src/prompts/`)

Created a prompt module system mirroring the existing steerer plugin architecture. Each prompt is a Python class with two methods:

- `system_prompt() -> str` — the system prompt sent to the LLM
- `parse_response(raw_json) -> list[dict]` — normalizes whatever JSON the LLM returns into a list of insight dicts, each with a required `"insight"` key plus any extra metadata

**Files created:**
- `src/prompts/__init__.py` — `PromptModule` protocol and `load_prompt(name)` loader
- `src/prompts/default.py` — wraps the original hardcoded synthesizer prompt (backward compatible, expects JSON array of `{"text": "..."}`)
- `src/prompts/insight_generating.py` — user's psychiatry-style prompt refactored into a class. Returns single JSON object with `insight`, `confidence` (0-10), and `suggestedAction`

**CLI integration:** `--prompt <name>` flag in `run.py` (default: `"default"`). Example: `--prompt insight_generating`

### 2. Synthesizer Updated (`src/synthesizer.py`)

- Accepts a `prompt_module` parameter (defaults to `DefaultPrompt` for backward compat)
- Uses `prompt_module.system_prompt()` instead of the old hardcoded `SYSTEM_PROMPT` constant
- Passes parsed LLM JSON through `prompt_module.parse_response()` to get normalized insights
- Stores the full raw LLM JSON response in each insight's metadata as `prompt_result` for traceability
- Extra fields from parse_response (e.g., `confidence`, `suggestedAction`) are merged into metadata
- Removed the hardcoded `SYSTEM_PROMPT` constant

### 3. HTML Visualization Upgrades (`src/visualizer.py`)

**Color fix:** Replaced the fixed 15-color `PALETTE` array (which cycled via modulo, causing color repetition at 16+ clusters) with golden-angle HSL generation: `hue = clusterId * 137.508 % 360`. This produces visually distinct colors for any number of clusters.

**Insight rendering:** When insights exist in the pipeline result:
- Computes centroid position of each cluster's points
- Adds insight points at centroids as `OctahedronGeometry` (diamond shape) at 2x sphere radius
- Brighter emissive intensity (0.6 vs 0.3) with white-tinted surface color
- Multiple insights for the same cluster are offset along y-axis to avoid overlap

**Toggle control:** "Show Insights" checkbox in bottom-right panel. Toggles visibility of all insight meshes and excludes hidden insights from raycaster hover detection.

**Legend update:** Added an "Insights" entry at the bottom of the legend with a diamond-shaped swatch (CSS-rotated square) and total count. Cluster entries now exclude insight points from their counts.

**Tooltips:** Insight hover shows gold (`#d4a017`) "Insight (Cluster N)" tag instead of the regular cluster color tag. Tooltip text includes confidence and suggested action when available.

### 4. Output File Changes (`src/io.py`)

**`cluster_texts.md`** (was `cluster_texts.json`): Converted from JSON to human-readable markdown. Structure per cluster:
- `# Cluster N (X texts)` header
- `## Insights` section with blockquoted insight text, confidence, and suggested action (omitted when no insights exist)
- `## Texts` section with numbered texts separated by horizontal rules
- Texts sorted by timestamp (ascending) as before

**`insights.json`** enriched: Now includes `confidence`, `suggestedAction`, and the full `prompt_result` object alongside the existing `insight`, `cluster_id`, and `source_memories` fields.

### 5. CLI Updates (`run.py`)

- Added `--prompt` argument with help text listing available prompts
- Prompt module loaded and passed to `AnthropicSynthesizer`
- `prompt` field added to `run_config` saved in `run_info.json`
- Print statement updated: `cluster_texts.json` → `cluster_texts.md`

## Files Changed
- `src/prompts/__init__.py` — **new** — prompt protocol and loader
- `src/prompts/default.py` — **new** — default prompt (original behavior)
- `src/prompts/insight_generating.py` — **new** — psychiatry-style prompt with confidence
- `src/synthesizer.py` — **modified** — uses pluggable prompt module
- `src/visualizer.py` — **modified** — color fix, insight rendering, toggle, legend
- `src/io.py` — **modified** — markdown cluster_texts, enriched insights.json
- `run.py` — **modified** — `--prompt` flag, updated print
- `tests/test_io.py` — **modified** — 4 new tests for markdown output and enriched insights
- `tests/test_prompts.py` — **new** — 9 tests for prompt loading and parsing

## Test Results
39/39 tests passing (was 26, added 13 new).

## Verified With
- `python run.py data/sample_input.jsonl --cluster-only` — confirmed markdown output, color fix, no API cost
- All output files generated correctly in run directory
