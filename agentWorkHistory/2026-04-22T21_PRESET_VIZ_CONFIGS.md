# PRESET_VIZ_CONFIGS — Preset Configurations for Blog-Ready Visualizations — 2026-04-22

## What was built

A preset system for the single-run 3D visualizations (`src/visualizer.py`) that lets you configure a viz interactively — pin interesting points, set the camera angle, toggle clustering off — then "freeze" that state so the HTML file loads pre-configured. Designed for embedding visualizations in blog posts.

---

## 1. Preset Infrastructure

### Problem

Every generated `viz.html` loaded in a blank state: no points highlighted, default camera, all UI toggles at defaults. Preparing a viz for a blog post required the reader to manually explore from scratch.

### Solution

Added a `PRESETS` JSON constant to the HTML template. When present, `applyPresets()` runs before the first render and restores:
- **Pinned tooltips** — specific points pre-pinned with chosen colors and tooltip positions
- **Camera position/target** — exact view angle and zoom level
- **Toggle states** — clustering and insights on/off

### Preset schema

```json
{
  "pins": [
    { "pointId": "uuid", "color": "#f47", "offset": { "x": 0.015, "y": -0.02 } }
  ],
  "camera": {
    "position": { "x": 1.2, "y": 0.8, "z": 1.5 },
    "target": { "x": 0, "y": 0, "z": 0 }
  },
  "clustering": false,
  "insights": true,
  "ui": { "config": false, "controls": false }
}
```

### Modified files

- **`src/visualizer.py`** — Added `presets` parameter to `generate_viz_html()`, `__PRESETS_JSON__` template variable, `applyPresets()` JS function
- **`src/io.py`** — Added `presets` parameter pass-through in `save_run()`

---

## 2. "Copy Preset JSON" Button

### Problem

Manually constructing preset JSON (looking up point UUIDs, camera coordinates) would be tedious and error-prone.

### Solution

Added a "Copy Preset JSON" button to the controls panel. Clicking it serializes the current interactive state — all pinned points with their IDs, colors, and offsets, plus camera position/target and toggle states — to the clipboard as JSON. Visual feedback: button turns green and shows "Copied!" for 2 seconds.

### Modified file

- **`src/visualizer.py`** — Button HTML in controls section, click handler using `navigator.clipboard.writeText()`

---

## 3. Tooltip UX Upgrades

### Problem

Pinned tooltips used absolute screen-pixel positioning and didn't move when the camera rotated, making them disconnect from their points. They also couldn't be repositioned.

### Solution

- **Offset-from-projection positioning**: Tooltips are now positioned relative to their point's 3D-projected screen position. `updatePinLines()` repositions both the dot and the tooltip every frame, so they track with camera rotation.
- **Draggable tooltips**: Pinned tooltips can be grabbed and dragged to reposition. CSS `cursor: grab/grabbing` provides visual affordance.
- **Extracted `createPin()` helper**: Pin-creation logic pulled out of the click handler into a reusable function, shared by both click-to-pin and preset application.

### Modified file

- **`src/visualizer.py`** — `updatePinLines()` upgraded, `createPin()` extracted, drag event handlers added, CSS for `.dragging`

---

## 4. Post-Hoc Preset Injection Script

### Problem

Presets need to be applied to already-generated HTML files. Re-running the pipeline would produce different UUIDs, UMAP coordinates, and clusters — destroying the state you want to preserve.

### Solution

Created `scripts/apply_preset.py` — a standalone script that patches an existing HTML file by replacing `const PRESETS = null;` with the preset JSON via regex.

```bash
python scripts/apply_preset.py viz.html preset.json -o blog.html
python scripts/apply_preset.py viz.html --preset '{"pins": [...]}' -o blog.html
```

Fails explicitly on old HTML files that lack the `PRESETS` variable.

### New file

- **`scripts/apply_preset.py`**

---

## 5. UI Overlay Hiding

### Problem

For blog embedding, the configuration panel, clustering/insights toggles, legend, help text, and title are clutter — the reader just wants a clean interactive chart.

### Solution

Added CLI flags to `scripts/apply_preset.py`:
- `--hide-config`, `--hide-controls`, `--hide-legend`, `--hide-info`, `--hide-title` — hide individual UI elements
- `--clean` — hides all five at once

Implemented by injecting CSS `display: none !important` rules directly into the HTML `<style>` block, so it works on any viz file regardless of template version (not dependent on JS-side `applyPresets()`).

```bash
python scripts/apply_preset.py viz.html preset.json --clean -o blog.html
```

### Modified file

- **`scripts/apply_preset.py`** — Added argparse flags and CSS injection in `apply_preset()`

---

## 6. Viewport-Responsive Pinned Tooltips

### Problem

Pinned tooltips used fixed pixel sizes for font, padding, max-width, and positioning offsets. When embedded in a blog post iframe at a different size than the authoring window, tooltips appeared too large or too small.

### Solution

- **CSS**: Switched `.pinned-tooltip` from `px` to `vw`/`em` units: `font-size: max(0.9vw, 10px)`, `padding: 0.75em 1em`, `max-width: 25vw`. Pin dots also scale via `vw` with a `px` floor.
- **Pin offsets**: Changed from pixel values to viewport fractions (0–1 range). Stored as fractions internally and in preset JSON; converted to pixels at render time via `offset * innerWidth/Height`.
- **Backward compatibility**: `applyPresets()` auto-detects old pixel offsets (abs > 2) and converts them to fractions on load.

### Modified file

- **`src/visualizer.py`** — CSS changes, offset math in `createPin()`, `updatePinLines()`, drag handler, click handler, and copy preset serialization

---

## Complete workflow

1. Run pipeline: `python run.py data/input.jsonl`
2. Open `output/run_.../viz.html` in browser
3. Explore: rotate camera, pin points, toggle clustering, drag tooltips
4. Click **"Copy Preset JSON"** → paste into `preset.json`
5. Apply: `python scripts/apply_preset.py output/run_.../viz.html preset.json --clean -o blog.html`
6. Embed `blog.html` in blog post — loads pre-configured with clean UI

## Files changed

| File | Change |
|------|--------|
| `src/visualizer.py` | Presets param, template variable, createPin helper, tooltip offset/drag/scaling, copy button, applyPresets |
| `src/io.py` | Presets pass-through in save_run |
| `scripts/apply_preset.py` | New — preset injection + UI hiding CLI |
