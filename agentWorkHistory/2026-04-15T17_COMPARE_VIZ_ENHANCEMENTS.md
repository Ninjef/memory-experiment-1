# COMPARE_VIZ_ENHANCEMENTS — Procrustes Alignment, Tooltip UX, and Insight Nodes — 2026-04-15

## What was built

Several enhancements to `scripts/compare_runs.py` to make the run comparison visualization suitable for blog posts and video walkthroughs. All changes were confined to this single file.

---

## 1. Procrustes Alignment

### Problem

Each run's `viz_coords.csv` comes from an independently-fit UMAP, so coordinate frames differ in rotation, reflection, translation, and scale. This caused:
- Runs with smaller natural extent (e.g., runs 1 and 2) appeared as tiny blobs while run 200 filled the viewport
- The cluster centroid drifted across transitions, making it look like the whole cloud was lurching rather than individual points shifting
- Transitions involved visible rotation/reflection flips

### Solution

Added `align_runs_to_reference()` — a closed-form ordinary Procrustes alignment via SVD. For each run k>=1, it:
1. Finds shared points with run 0 by text hash
2. Computes optimal rotation R (with reflection allowed), uniform scale s, and translation t minimizing sum ||s R x_i + t - y_i||^2
3. Applies the transform to all points in run k (not just shared ones)

Run 0 is the reference frame; all others are mapped into it. After alignment, the existing global bounding box logic produces correct camera framing because all runs live in the same coordinate space.

### Key design decisions

- **Reflection allowed** (`det(R)` not forced to +1) — UMAP output can legitimately be mirrored, so preventing reflection would leave some runs misaligned
- **Direct alignment to run 0** rather than chaining pairwise (run k -> k-1 -> ... -> 0) — all config runs share the same memory corpus, so direct overlap is plentiful and avoids compounding errors
- **Minimum 3 shared points** required for a stable fit (3D data needs >=3 non-collinear points); runs below threshold are left in their native frame with a stderr warning

### Modified file

- **`scripts/compare_runs.py`** — Added `import numpy as np`, `align_runs_to_reference()` function (~60 lines), wired into both `build_payload_single` and `build_payload_side_by_side` before `match_points`

---

## 2. Slider Label Alignment

### Problem

Slider tick labels used `display: flex; justify-content: space-between`, which spread labels evenly across the container width. But HTML range input thumbs don't travel the full width — they're inset by half the thumb width on each side. Labels didn't line up with where the thumb actually sits at each discrete step.

### Solution

Switched to absolute positioning with `calc()` that accounts for thumb travel range:

```javascript
const THUMB_W = 14;
function positionLabel(span, i, n) {
  const pct = n === 1 ? 50 : (i / (n - 1)) * 100;
  span.style.left = `calc(${pct}% + ${(0.5 - pct / 100) * THUMB_W}px)`;
}
```

Each label is absolutely positioned with `transform: translateX(-50%)` for centering, and the `calc()` expression offsets by the correct fraction of thumb width at each position.

### Modified file

- **`scripts/compare_runs.py`** — CSS changed from flex to `position: relative`, JS added `positionLabel()` helper applied to both top and bottom label rows

---

## 3. Tooltip Enhancements

### Problem

- Pinned tooltips stayed fixed at their click position; only the dot and connector line tracked the node during transitions
- Only one tooltip could be dragged (a missing `getBoundingClientRect()` call caused a JS error that broke the update loop)
- Colors were auto-assigned with no way to change them

### Solution

Three improvements:

**Following nodes**: `_updatePinLines()` now repositions each tooltip's `el` to `(scr.x + offset.x, scr.y + offset.y)` every frame, where `scr` is the mesh's screen projection. The existing connector line logic (which reads `getBoundingClientRect()`) adapts automatically.

**Draggable tooltips**: Each tooltip stores a `pinOffset` object `{x, y}` (initially `{16, 16}`). Mousedown on the tooltip body (excluding close button, color toggle, and swatches) starts a drag that updates `pinOffset` based on mouse delta. The offset is per-tooltip (closure-scoped), so multiple tooltips can be arranged independently.

**Color picker dropdown**: A small "color" toggle link with a colored indicator dot is appended to each tooltip. Clicking it reveals/hides a row of color swatches (the same 10-color PIN_COLORS palette). Clicking a swatch updates the tooltip border, dot, connector line, and 3D mesh color, then auto-closes the swatch row.

### Bug fix

The `_updatePinLines()` method was missing `const rect = pin.el.getBoundingClientRect();` after an earlier edit added tooltip following. This caused a `ReferenceError` on every frame, which:
- Broke connector lines entirely (the `setAttribute` calls for line endpoints never ran)
- Prevented multi-tooltip dragging (the error on the first tooltip's update killed the loop before processing subsequent tooltips)

### Modified file

- **`scripts/compare_runs.py`** — CSS: added `cursor: grab`, `user-select: none`, `.dragging` class, color toggle/swatch styles. JS: drag handler on tooltip mousedown, `pinOffset` stored per pin, `_updatePinLines()` repositions tooltip and recomputes `getBoundingClientRect()` each frame, color toggle and swatch row creation in pin handler.

---

## 4. Insight / Idea Node Support

### Problem

Some runs produce `insights.json` containing synthesized ideas positioned at cluster centroids. These were shown in the single-run visualizer (`src/visualizer.py`) as diamond-shaped nodes but were absent from the comparison tool.

### Solution

**Python — `load_insights()` function**: Reads `insights.json` from a run directory, computes cluster centroids from the memory rows, and returns rows with `type: "insight"` positioned at centroids (with y-axis offsets for multiple insights per cluster). Insight tooltip text shows only the idea text (no confidence score or suggested action).

**Python — `match_points()` update**: Now carries a `type` field (`"memory"` or `"insight"`) through to the payload so JS knows which geometry to use.

**Python — payload builders**: `build_payload_single` and `build_payload_side_by_side` now call `load_insights()` for each run and merge the rows into `all_runs_rows` before alignment and matching.

**JS — diamond rendering**: Insight nodes use `THREE.OctahedronGeometry` (2x the sphere radius), white color, lower roughness (0.3), higher emissive intensity (0.6). They keep their white color during transitions and recoloring (skipped in `_recolorAll()` and `_applyInterpolation()`).

**JS — type tags**: Both hover and pinned tooltips show a colored type tag before the cluster tag: blue "Memory" for regular embeddings, gold "New Idea" for insight nodes.

### Key design decisions

- Insights don't match across runs by text hash (they're unique per run), so they appear/disappear with fade-in/fade-out as you slide between runs
- Insight rows are included in Procrustes alignment input but have minimal impact since they're positioned at centroids (close to the mass of memory points they summarize)
- The `load_insights()` function mirrors the centroid computation from `src/visualizer.py` for consistency

### Modified file

- **`scripts/compare_runs.py`** — Added `load_insights()` (~65 lines), updated `load_coords()` to include `type: "memory"`, updated `match_points()` to carry `type`, updated payload builders, JS mesh creation uses `OctahedronGeometry` for insights, `_recolorAll()` and `_applyInterpolation()` skip recoloring insights, type tag CSS and HTML added to both hover and pinned tooltips

---

## Tests

All 17 existing tests in `tests/test_compare_runs.py` continue to pass. No new test file was needed — the changes are in rendering logic (HTML/JS template) and data loading that is exercised by the existing payload construction tests.
