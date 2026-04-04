# FIFTH_STEP Implementation — 2026-04-04

## What was built

Three pieces of work in this session: pluggable clusterer system, visualization improvements, and a new steerer variant.

---

## 1. Pluggable Clusterers System

Brought clusterers to the same pluggable module pattern already used by steerers and prompts.

### New files
- **`src/clusterers/__init__.py`** — Dynamic loader (`load_clusterer_module(name)`) mirroring `src/steerers/__init__.py`
- **`src/clusterers/umap_hdbscan.py`** — Existing `UMAPHDBSCANClusterer` moved here from `src/clusterer.py`, with `add_args()` and `create()` module functions added to match the steerer pattern
- **`src/clusterers/theme_nn.py`** — New theme-based nearest-neighbor clusterer (see below)

### Modified files
- **`run.py`** — Replaced hardcoded clusterer instantiation with two-phase dynamic loading (same pattern as steerers). The `--clusterer` arg now accepts any module name from `src/clusterers/`. Clusterer-specific args (like `--min-cluster-size` for umap_hdbscan) are now registered by the clusterer module itself.

### Deleted files
- **`src/clusterer.py`** — Replaced by `src/clusterers/umap_hdbscan.py`

### Theme Nearest-Neighbor Clusterer (`theme_nn`)

This is the alternative clustering approach described in FIFTH_STEP.md — instead of discovering clusters via UMAP+HDBSCAN, you supply theme strings and the clusterer assigns each chunk to the theme it's most similar to (by cosine similarity).

**How it works:**
1. Embed the theme strings using the same model as chunks
2. Compute cosine similarity between each chunk and each theme
3. Assign each chunk to its best-matching theme if similarity exceeds `--theme-threshold` (default 0.3)
4. Chunks below threshold go to noise (-1), consistent with HDBSCAN convention
5. Optional `--theme-top-k` limits neighbors per theme

**Design decision — CLI arg naming:** Theme args use the `--cluster-themes` / `--cluster-themes-file` prefix (not `--themes`) to avoid conflicts with the projection steerer's `--themes` arg. Both can coexist in the same run.

**Usage:**
```bash
python run.py data/sample_input.jsonl --clusterer theme_nn \
  --cluster-themes "technology" "food" --theme-threshold 0.15 --cluster-only
```

---

## 2. Visualization Improvements

### Run name in HTML (`src/visualizer.py`, `src/io.py`)

The auto-generated run folder name (e.g., `run_20260404_002049_lunar-kerfuffle`) now appears in the HTML visualization:
- In the browser tab `<title>`
- As a visible header in the top-left corner of the 3D view
- For steered dual-view runs, appended with " — Steered Embedding Space" / " — Original Embedding Space"

### Configuration panel (`src/visualizer.py`, `src/io.py`)

A new panel on the left side of the visualization (below the run name) displays all configuration parameters used for the run. This includes top-level config (model, embedder, clusterer, steerer, prompt) and nested parameter sections (e.g., `clusterer_params` with theme settings). The `run_config` dict is passed from `save_run()` through to `generate_viz_html()` and embedded as JSON in the HTML.

---

## 3. Projection-Normalize Steerer (`src/steerers/projection_normalize.py`)

A variant of the `projection` steerer that L2 re-normalizes embeddings after steering. The original `projection` steerer amplifies theme-aligned components but leaves magnitude inflated — embeddings that align with themes end up with ||v|| > 1 while others stay near 1. This magnitude difference persists into UMAP/HDBSCAN clustering.

The `projection_normalize` steerer applies the same projection math, then divides by ||v|| so all embeddings return to unit length. This means steering only rotates embeddings toward themes without changing their magnitude.

**When to use which:**
- `projection` — steering affects both direction and magnitude (magnitude acts as implicit weighting in UMAP)
- `projection_normalize` — steering affects direction only (purer directional signal, no magnitude bias)

Same CLI args as `projection`: `--themes`, `--themes-file`, `--steer-alpha`.

**Usage:**
```bash
python run.py data/sample_input.jsonl --steerer projection_normalize \
  --themes "technology" "food" --cluster-only
```

---

## Verification

All changes tested end-to-end:
- Default path (`python run.py data/sample_input.jsonl --cluster-only`) works identically to before
- Theme clusterer produces expected clusters with tunable threshold
- Run name and config panel render correctly in HTML output
- Projection-normalize steerer runs successfully and produces different cluster assignments than the unnormalized variant
