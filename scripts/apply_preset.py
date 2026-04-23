#!/usr/bin/env python3
"""Inject a preset configuration into an existing visualization HTML file.

Usage:
    python scripts/apply_preset.py viz.html preset.json [-o output.html]
    python scripts/apply_preset.py viz.html --preset '{"pins": [...], ...}'
    python scripts/apply_preset.py viz.html preset.json --clean -o blog.html

If -o is not specified, the input file is overwritten in place.
"""

import argparse
import json
import re
import sys
from pathlib import Path


_UI_ID_MAP = {
    "config": "config-panel",
    "controls": "controls",
    "legend": "legend",
    "info": "info",
    "title": "run-name",
}


def apply_preset(html: str, preset: dict) -> str:
    """Replace ``const PRESETS = ...;`` with the provided preset JSON."""
    preset_json = json.dumps(preset)
    pattern = r"const PRESETS = .+?;"
    result, count = re.subn(pattern, f"const PRESETS = {preset_json};", html, count=1)
    if count == 0:
        print(
            "Error: Could not find 'const PRESETS = ...' in the HTML file.\n"
            "This file may not have been generated with preset support.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Inject CSS to hide UI elements — works on any viz version
    ui = preset.get("ui", {})
    hide_ids = [_UI_ID_MAP[k] for k, v in ui.items() if v is False and k in _UI_ID_MAP]
    if hide_ids:
        css_rules = " ".join(f"#{eid} {{ display: none !important; }}" for eid in hide_ids)
        result = result.replace("</style>", f"  {css_rules}\n</style>", 1)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject preset config into a viz HTML file",
    )
    parser.add_argument("html_file", help="Path to the visualization HTML file")
    parser.add_argument("preset_file", nargs="?", help="Path to preset JSON file")
    parser.add_argument(
        "--preset", help="Preset JSON as a string (alternative to file)"
    )
    parser.add_argument(
        "-o", "--output", help="Output path (default: overwrites input)"
    )

    # UI visibility flags
    ui_group = parser.add_argument_group("UI visibility")
    ui_group.add_argument(
        "--clean",
        action="store_true",
        help="Hide all UI overlays (config, controls, legend, info, title)",
    )
    ui_group.add_argument(
        "--hide-config", action="store_true", help="Hide the configuration panel"
    )
    ui_group.add_argument(
        "--hide-controls",
        action="store_true",
        help="Hide the controls panel (clustering/insights toggles, copy preset)",
    )
    ui_group.add_argument(
        "--hide-legend", action="store_true", help="Hide the cluster legend"
    )
    ui_group.add_argument(
        "--hide-info", action="store_true", help="Hide the bottom help text"
    )
    ui_group.add_argument(
        "--hide-title", action="store_true", help="Hide the run name title"
    )
    args = parser.parse_args()

    html_path = Path(args.html_file)
    html = html_path.read_text(encoding="utf-8")

    if args.preset:
        preset = json.loads(args.preset)
    elif args.preset_file:
        preset = json.loads(Path(args.preset_file).read_text(encoding="utf-8"))
    else:
        preset = {}

    # Apply UI visibility flags to the preset
    ui = preset.get("ui", {})
    if args.clean:
        for key in ("config", "controls", "legend", "info", "title"):
            ui.setdefault(key, False)
    else:
        if args.hide_config:
            ui["config"] = False
        if args.hide_controls:
            ui["controls"] = False
        if args.hide_legend:
            ui["legend"] = False
        if args.hide_info:
            ui["info"] = False
        if args.hide_title:
            ui["title"] = False
    if ui:
        preset["ui"] = ui

    if not preset:
        print(
            "Error: Provide a preset file, --preset JSON string, or UI flags",
            file=sys.stderr,
        )
        sys.exit(1)

    result = apply_preset(html, preset)

    output_path = Path(args.output) if args.output else html_path
    output_path.write_text(result, encoding="utf-8")
    print(f"Preset applied to {output_path}")


if __name__ == "__main__":
    main()
