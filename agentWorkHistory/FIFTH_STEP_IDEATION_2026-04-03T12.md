# FIFTH_STEP — Ideation Session: Verification Strategy & Next Steps

**Date:** 2026-04-03
**Task:** `projectTasks/FIFTH_STEP.md`
**Type:** Ideation session (no code changes)

## Context

The pipeline is functionally complete through step 4. The core question now is: **does the steering mechanism actually produce true, novel insights that wouldn't surface without it?** This session explored how to answer that question.

## Project Assessment

Reviewed the full project arc from IDEA_OVERVIEW through all completed steps. Key observations:

- The engineering is solid for a research prototype — pluggable steerers, prompts, and good visualization
- Steering has been shown to predictably pull distant clusters together (confirmed in FOURTH_STEP observations)
- The unvalidated assumption: whether forced co-location of distant clusters produces insights that are both **true** and **novel**, vs. plausible-sounding narratives the LLM would generate from any random grouping

## Directions Considered

Four possible directions were discussed:

1. **Verification-first (scientific rigor)** — build evaluation framework, use ground-truth data, measure steered vs. unsteered insight quality. **Selected as the path forward.**
2. **Product-first (practical utility)** — skip rigorous verification, build toward a usable personal memory tool
3. **Research depth** — go deeper on the steering math (nonlinear steering, learned embeddings, etc.)
4. **Benchmark creation** — create a public dataset for testing cross-domain insight generation

Decision: Direction 1 is the critical path. Without verification, other directions build on unvalidated assumptions.

## Verification Plan

### Data Strategy

Use personal data where the user has complete ground truth knowledge of themselves:

- **Tier 1 — Journal entries:** Purest signal. Start with 10-15 entries spanning different life domains. Don't let full digitization block experimentation.
- **Tier 2 — AI chat logs (user's side):** High volume, low effort to collect. AI responses should be tagged but filterable to avoid false positives from the AI's own synthesis.
- **Tier 3 — Personal documents/essays:** Useful but filtered through professional voice.

### Raw Text Format Decided

Simple markdown files with YAML frontmatter:

```markdown
---
date: 2025-11-15
source: journal
author: me
---

Text content here, paragraph by paragraph.
```

For chat logs, `[me]` and `[ai]` speaker tags at line starts. Chunker splits on paragraphs (single-author) or speaker turns (chats). AI turns can be filtered out via flag.

### Engineering Plan (not yet built)

Three new components, all modular and separate from the core pipeline:

1. **Chunker** — reads the markdown+frontmatter files from a personal data directory, splits into pipeline-ready JSONL with metadata preserved
2. **Comparison/rating tool** — standalone script that takes N output directory paths, presents insights for rating (true/false/partial, novel/obvious/wrong), stores ratings as JSON within each run's directory
3. **Analysis script** — reads rating files across runs, computes steered-vs-unsteered deltas

Key design decisions:
- One unsteered baseline run is sufficient (deterministic embeddings/clustering), compared against multiple steered variants
- Comparison tool is fully decoupled from the pipeline — operates on output directories, not integrated into `run.py`
- This keeps the core pipeline single-purpose and allows different post-processing/analysis tools to be built independently

## Next Steps

1. User to begin preparing personal text data (journal entries + AI chat logs)
2. Build the chunker for the markdown+frontmatter format
3. Build the comparison/rating tool
4. Run steered vs. unsteered experiments and rate insights
