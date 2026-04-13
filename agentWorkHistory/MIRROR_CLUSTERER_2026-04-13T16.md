# MIRROR_CLUSTERER — Cluster Mirroring for Blog Visualizations — 2026-04-13

## What was built

A new `mirror` clusterer module that copies cluster assignments from a previous run's output, enabling side-by-side visualizations with consistent cluster colors across runs (e.g., before/after embedding steering).

---

## 1. Mirror Clusterer (`src/clusterers/mirror.py`)

### Problem

For the blog post, we need to show readers how the embedding space shifts when steering is applied. To make this comparison meaningful, the cluster assignments and colors must remain identical across the two visualizations — only the 3D positions should change.

### Solution

A new clusterer plugin (`--clusterer mirror`) that reads `clusters.json` from a previous run and assigns chunks to the same cluster IDs. Since the visualizer uses deterministic golden-angle HSL coloring based on cluster ID, matching IDs guarantees matching colors.

### Key design decisions

- **Text-based matching with ID fallback**: Input JSONL files typically lack an `id` field, so each run generates fresh random UUIDs. The mirror clusterer matches chunks by text content first, falling back to chunk ID for cases where IDs are stable across runs.
- **Fresh UMAP coordinates**: `reduce_for_viz()` computes new 3D coordinates from the current (possibly steered) embeddings rather than copying from the base run — this is the whole point, showing how positions change.
- **Graceful mismatch handling**: Warns on chunks present in only one run (base-only are skipped, current-only go to noise cluster -1). Logs an error if zero chunks match.

### CLI usage

```bash
# 1. Baseline run
python run.py data.jsonl --clusterer umap_hdbscan --output-dir output/baseline

# 2. Steered run with mirrored clusters
python run.py data.jsonl --clusterer mirror --mirror-base-dir output/baseline \
    --steerer projection --themes "self-actualization" --cluster-only
```

### New files
- `src/clusterers/mirror.py` — MirrorClusterer class + CLI integration (~130 lines)

### Modified files
- None — leverages the existing clusterer plugin system with zero changes to existing code.
