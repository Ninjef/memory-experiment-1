# Overview

The run comparison visualization (`scripts/compare_runs.py`) needs several improvements for blog and video presentation purposes.

# Requirements

## Coordinate Alignment (Procrustes)
- The animated transitions between runs look jarring because each run's UMAP embedding has its own arbitrary rotation, reflection, translation, and scale
- The zoom level changes dramatically between runs (some runs appear as tiny blobs, others fill the screen)
- The cluster centroid should stay roughly fixed across transitions; individual points should shift, not the whole cloud
- Apply Procrustes alignment so all runs share a consistent coordinate frame

## Slider Label Alignment
- The slider tick labels don't line up with the actual slider thumb positions at each discrete step
- Fix label positioning to match where the thumb actually sits

## Tooltip Improvements
- Pinned tooltips should follow their associated nodes during transitions (currently they stay fixed and only the connector line moves)
- Tooltips should be draggable so multiple can be arranged for readability
- Each tooltip should allow the user to choose its color via a dropdown (hidden by default to keep things clean)
- Connector lines from tooltips to nodes must remain visible and functional

## Insight / Idea Node Support
- Runs that have `insights.json` should display those ideas as diamond-shaped (octahedron) nodes positioned at cluster centroids
- Insight nodes should be white, larger, and shinier than regular memory nodes
- Tooltips should distinguish between "Memory" (regular embeddings) and "New Idea" (insights) with a colored type tag
- Insight tooltips should show only the idea text, not confidence scores or suggested actions

# Considerations
- All changes should be in `scripts/compare_runs.py` only (Python data processing + inline HTML/JS template)
- Procrustes alignment should use shared points (matched by text hash) as correspondences
- Insight nodes won't match across runs by text (they're unique per run) — they should appear/disappear as you slide
- The alignment should only use memory nodes as correspondences, not insights
- numpy is already available for the SVD computation
