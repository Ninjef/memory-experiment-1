# INTERACTIVE_VISUALIZATION — Run Comparison Tool & Viz Enhancements — 2026-04-08

## What was built

A standalone post-processing tool that generates interactive HTML comparisons of multiple pipeline runs, plus several UX enhancements to both the existing single-run visualizer and the new comparison tool.

---

## 1. Run Comparison Tool (`scripts/compare_runs.py`)

### Problem

Each pipeline run produces its own standalone `viz.html` with a 3D scatter plot, but there was no way to visually compare how the same memory points move across runs with different configurations (e.g., different steering alphas or clusterers).

### Solution

A Python CLI tool that reads a JSON config file specifying run directories, matches points across runs by text content, and generates a self-contained HTML file with a slider that animates point transitions between runs.

### New files

- **`scripts/compare_runs.py`** — Standalone CLI tool (~880 lines including HTML template). No dependency on `src/pipeline.py`; reads CSV/JSON directly from output directories.
  - Config-driven: single JSON file specifies run paths, labels, coords file, and optional side-by-side layout
  - Point matching via SHA-256 hash of text content (16 hex chars), collision-safe
  - Discrete slider with time-based animated transitions (800ms ease-in-out cubic)
  - Points missing from a run fade in/out during transitions
  - Cluster colors snap at animation midpoint
  - Global bounding box across all runs for stable camera framing
  - Side-by-side mode: two independent Three.js panels with a shared slider, each with its own runs and coordsFile
  - Output: timestamped directory with HTML + config copy for reproducibility
- **`tests/test_compare_runs.py`** — 17 unit tests covering text hashing, CSV loading, point matching (full overlap, partial overlap, collisions, text truncation), config validation (basic, side-by-side, error cases), and payload construction

### Config file format

```json
{
  "coordsFile": "viz_coords.csv",
  "runs": [
    {"path": "output/run_..._frothy-penguin", "label": "No Steering"},
    {"path": "output/run_..._wobbly-meteor", "label": "Alpha=100"}
  ]
}
```

Side-by-side mode adds a `sideBySide` object with `left`/`right` sections, each with their own `title`, `runs`, and optional `coordsFile` override.

### Usage

```bash
python scripts/compare_runs.py compare_config.json
# -> output/compare_YYYYMMDD_HHMMSS/compare.html
```

---

## 2. Random Assignment Clusterer (`src/clusterers/random_assign.py`)

### Problem

Needed a baseline clusterer for testing visualizations and comparisons without depending on HDBSCAN behavior.

### Solution

A clusterer that divides N chunks into ~N/15 clusters by randomly assigning each chunk using Dirichlet-weighted probabilities. This produces clusters of naturally varying sizes without any single cluster dominating (unlikely to exceed ~70% of points).

### New files

- **`src/clusterers/random_assign.py`** — Follows the standard clusterer module interface (`add_args`, `create`, class with `cluster` and `reduce_for_viz`).
  - `--chunks-per-cluster` (default 15): controls number of clusters
  - `--dirichlet-alpha` (default 2.0): controls size variance
  - `--random-seed`: optional reproducibility
  - Uses UMAP for visualization coordinates (same as other clusterers)

### Usage

```bash
python run.py --clusterer random_assign [--chunks-per-cluster 15] [--dirichlet-alpha 2.0]
```

---

## 3. Click-to-Pin Tooltips

### Problem

Hovering over a point showed its text, but you could only see one at a time and it disappeared when you moved away.

### Solution

Added click-to-pin functionality to both `src/visualizer.py` and `scripts/compare_runs.py`:

- **Click a point** to pin its text tooltip on screen permanently
- **Click multiple points** to see all their texts simultaneously
- **Color-coded associations**: each pinned tooltip gets a unique color from a 10-color palette, applied to:
  - The tooltip border
  - A connector line (SVG) from the tooltip to the node
  - A dot overlay on the node's screen position
  - The 3D mesh itself (painted the pin color)
- Connector lines and dots **update every frame** as you rotate/zoom the camera
- **Close individually** via X button (restores original mesh color) or **clear all** with Escape
- Drag detection: mouse must move < 5px to count as a click (not a camera drag)

### Modified files

- **`src/visualizer.py`** — Added pinned tooltip CSS, SVG overlay, click handler with color assignment, `updatePinLines()` called every frame, Escape handler
- **`scripts/compare_runs.py`** — Same features added to the `VizPanel` class with `_projectToScreen()` and `_updatePinLines()` methods

---

## 4. Clustering Toggle

### Problem

Cluster coloring dominates the visualization, making it hard to see the raw spatial distribution of points.

### Solution

Added a "Show Clustering" checkbox to both visualizers:

- **Checked (default)**: points colored by cluster, legend visible, cluster tags shown in tooltips
- **Unchecked**: all points turn a uniform bright blue (`#7ab8f5`), legend hidden, cluster tags removed from both hover and pinned tooltips

### Modified files

- **`src/visualizer.py`** — Added checkbox in controls panel, `applyClusterColors()` function, conditional cluster tag rendering
- **`scripts/compare_runs.py`** — Per-panel checkbox, `_colorFor()` and `_recolorAll()` methods, conditional tag rendering

---

## 5. Slider UX (Comparison Tool)

### Design decisions

- **Discrete stops** (one per run label) rather than continuous sliding
- Clicking a slider position triggers a **time-based 800ms animation** with ease-in-out cubic easing
- **Active label highlighted** (bold + full opacity), inactive labels dimmed
- Slider positioned compactly under the legend in the top-right panel (not a full-width bottom bar)
- In side-by-side mode, sliders are synced across panels
