# Overview
I am going to be putting some of the output interactive visualizations that come out of this repo into a blog post, and I'd like the visualizations to ALREAYDY have things like:
1. Text bubbles associated with selected text embeddings pre-selected
2. Other settings (like having the clustering turned off)
3. Some way for me to set these things up and save them (can I click bubbles, then click a "save" button? Is there a way for me to disable the save button in the HTML later? Or... if it's easy enough, could I just type in some presets in the HTML file itself for what's set at the beginning?)

# Post-script: Additional changes requested during implementation

- **UI overlay hiding via CLI flags**: Added `--hide-config`, `--hide-controls`, `--hide-legend`, `--hide-info`, `--hide-title`, and `--clean` flags to `scripts/apply_preset.py` so the generated blog viz can strip away all the development UI (configuration panel, clustering/insights toggles, etc.) and just be a clean interactive chart. Implemented via CSS injection so it works on any viz file regardless of template version.
- **Viewport-responsive pinned tooltips**: Changed pinned tooltip CSS from fixed `px` to `vw`/`em` units so text boxes, padding, and pin dots scale proportionally with the parent window size. Also changed pin offsets from pixel values to viewport fractions so tooltip positions scale correctly when embedded in iframes of different sizes. Backward-compatible with old pixel-based preset files (auto-detected and converted).
