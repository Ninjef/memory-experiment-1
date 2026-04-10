#!/usr/bin/env python3
"""Generate an interactive HTML comparison of multiple pipeline runs.

Reads a JSON config file specifying run directories and labels, matches
points across runs by hashing their text content, and produces a
self-contained HTML file with a slider that smoothly animates point
positions between runs using Three.js.

Usage:
    python scripts/compare_runs.py compare_config.json
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def text_hash(text: str) -> str:
    """SHA256 hash of text, truncated to 16 hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_coords(run_dir: Path, coords_file: str) -> list[dict]:
    """Load viz_coords CSV from a run directory.

    Returns list of dicts with keys: id, cluster_id, x, y, z, text.
    """
    csv_path = run_dir / coords_file
    if not csv_path.exists():
        raise FileNotFoundError(f"Coords file not found: {csv_path}")

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "id": row["id"],
                "cluster_id": int(row["cluster_id"]),
                "x": float(row["x"]),
                "y": float(row["y"]),
                "z": float(row["z"]),
                "text": row["text"],
            })
    return rows


def match_points(
    all_runs_rows: list[list[dict]],
) -> list[dict]:
    """Match points across runs by text hash.

    Returns a list of point dicts:
        {hash, text, positions: [{x, y, z, cluster} | None per run]}
    """
    # Build union of all text hashes
    hash_to_text: dict[str, str] = {}
    hash_to_positions: dict[str, list[dict | None]] = {}

    num_runs = len(all_runs_rows)

    for run_idx, rows in enumerate(all_runs_rows):
        seen_in_run: set[str] = set()
        for row in rows:
            h = text_hash(row["text"])
            # Collision handling: keep first encountered
            if h in seen_in_run:
                continue
            seen_in_run.add(h)

            if h not in hash_to_text:
                hash_to_text[h] = row["text"][:200]
                hash_to_positions[h] = [None] * num_runs

            hash_to_positions[h][run_idx] = {
                "x": round(row["x"], 5),
                "y": round(row["y"], 5),
                "z": round(row["z"], 5),
                "cluster": row["cluster_id"],
            }

    points = []
    for h, text in hash_to_text.items():
        points.append({
            "hash": h,
            "text": text,
            "positions": hash_to_positions[h],
        })

    return points


def load_config(config_path: Path) -> dict:
    """Load and validate the comparison config file."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    coords_file = config.get("coordsFile", "viz_coords.csv")
    side_by_side = config.get("sideBySide")

    if side_by_side:
        for side_key in ("left", "right"):
            side = side_by_side.get(side_key)
            if not side or not side.get("runs"):
                raise ValueError(
                    f"sideBySide.{side_key} must have a 'runs' array"
                )
            if len(side["runs"]) < 2:
                raise ValueError(
                    f"sideBySide.{side_key} must have at least 2 runs"
                )
            for run_entry in side["runs"]:
                if "path" not in run_entry:
                    raise ValueError(
                        f"Each run in sideBySide.{side_key} must have a 'path'"
                    )
    else:
        runs = config.get("runs")
        if not runs or len(runs) < 2:
            raise ValueError("Config must have at least 2 runs")
        for run_entry in runs:
            if "path" not in run_entry:
                raise ValueError("Each run must have a 'path'")

    return config


def build_payload_single(config: dict) -> dict:
    """Build the JSON payload for a single-view comparison."""
    coords_file = config.get("coordsFile", "viz_coords.csv")
    runs_config = config["runs"]

    runs_meta = []
    all_runs_rows = []

    for i, run_entry in enumerate(runs_config):
        run_dir = Path(run_entry["path"])
        label = run_entry.get("label", run_dir.name)
        runs_meta.append({"label": label, "index": i})
        all_runs_rows.append(load_coords(run_dir, coords_file))

    points = match_points(all_runs_rows)

    return {
        "mode": "single",
        "runs": runs_meta,
        "points": points,
    }


def build_payload_side_by_side(config: dict) -> dict:
    """Build the JSON payload for side-by-side comparison."""
    default_coords_file = config.get("coordsFile", "viz_coords.csv")
    sbs = config["sideBySide"]

    sides = {}
    for side_key in ("left", "right"):
        side_config = sbs[side_key]
        coords_file = side_config.get("coordsFile", default_coords_file)
        title = side_config.get("title", side_key.capitalize())

        runs_meta = []
        all_runs_rows = []

        for i, run_entry in enumerate(side_config["runs"]):
            run_dir = Path(run_entry["path"])
            label = run_entry.get("label", run_dir.name)
            runs_meta.append({"label": label, "index": i})
            all_runs_rows.append(load_coords(run_dir, coords_file))

        points = match_points(all_runs_rows)

        sides[side_key] = {
            "title": title,
            "runs": runs_meta,
            "points": points,
        }

    return {
        "mode": "sideBySide",
        "left": sides["left"],
        "right": sides["right"],
    }


def build_payload(config: dict) -> dict:
    """Build the full payload based on config mode."""
    if config.get("sideBySide"):
        return build_payload_side_by_side(config)
    return build_payload_single(config)


def generate_html(payload: dict) -> str:
    """Generate the self-contained HTML string."""
    data_json = json.dumps(payload)
    return _HTML_TEMPLATE.replace("__DATA_JSON__", data_json)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/compare_runs.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    payload = build_payload(config)

    # Create output directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = Path("output") / f"compare_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy config for reproducibility
    shutil.copy2(config_path, output_dir / "compare_config.json")

    # Generate HTML
    html = generate_html(payload)
    html_path = output_dir / "compare.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Print summary
    if payload["mode"] == "single":
        n_runs = len(payload["runs"])
        n_points = len(payload["points"])
        present_counts = []
        for i in range(n_runs):
            count = sum(
                1 for p in payload["points"] if p["positions"][i] is not None
            )
            present_counts.append(count)
        print(f"Runs: {n_runs}")
        print(f"Unique points (union): {n_points}")
        for i, run in enumerate(payload["runs"]):
            print(f"  {run['label']}: {present_counts[i]} points")
    else:
        for side_key in ("left", "right"):
            side = payload[side_key]
            print(f"{side['title']}:")
            print(f"  Runs: {len(side['runs'])}")
            print(f"  Unique points: {len(side['points'])}")

    print(f"\nOutput: {html_path}")


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Run Comparison</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #111; color: #eee; font-family: system-ui, sans-serif; overflow: hidden; }
  canvas { display: block; }

  #tooltip {
    position: absolute; pointer-events: none; display: none;
    background: rgba(0,0,0,0.85); color: #fff; padding: 10px 14px;
    border-radius: 6px; font-size: 13px; max-width: 360px;
    line-height: 1.4; border: 1px solid rgba(255,255,255,0.15);
    z-index: 100;
  }
  #tooltip .cluster-tag, .pinned-tooltip .cluster-tag {
    display: inline-block; padding: 2px 8px; border-radius: 3px;
    font-size: 11px; font-weight: 600; margin-bottom: 6px;
  }
  .pinned-tooltip {
    position: absolute; pointer-events: auto;
    background: rgba(0,0,0,0.9); color: #fff; padding: 10px 14px;
    border-radius: 6px; font-size: 13px; max-width: 360px;
    line-height: 1.4; border: 1px solid rgba(255,255,255,0.3);
    z-index: 90;
  }
  .pinned-tooltip .pin-close {
    position: absolute; top: 4px; right: 8px;
    cursor: pointer; opacity: 0.5; font-size: 14px;
  }
  .pinned-tooltip .pin-close:hover { opacity: 1; }
  .pin-lines {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 89;
  }
  .pin-dot {
    position: absolute; width: 8px; height: 8px;
    border-radius: 50%; border: 2px solid rgba(255,255,255,0.8);
    pointer-events: none; z-index: 91;
    transform: translate(-50%, -50%);
  }

  .viz-container {
    position: relative; width: 100vw; height: 100vh;
  }
  .viz-container.side-by-side {
    display: flex; width: 100vw; height: 100vh;
  }
  .viz-panel {
    position: relative; flex: 1; overflow: hidden;
  }
  .viz-panel + .viz-panel {
    border-left: 1px solid rgba(255,255,255,0.2);
  }
  .panel-title {
    position: absolute; top: 12px; left: 16px;
    font-size: 16px; font-weight: 600; opacity: 0.85;
    text-shadow: 0 1px 4px rgba(0,0,0,0.6); z-index: 10;
  }

  .legend {
    background: rgba(0,0,0,0.7); padding: 14px 18px;
    border-radius: 8px; font-size: 13px;
    border: 1px solid rgba(255,255,255,0.1);
    max-height: 50vh; overflow-y: auto;
  }
  .legend h3 { margin-bottom: 8px; font-size: 14px; }
  .legend-item { display: flex; align-items: center; margin: 4px 0; }
  .legend-swatch {
    width: 12px; height: 12px; border-radius: 50%;
    margin-right: 8px; flex-shrink: 0;
  }

  #run-label {
    position: absolute; top: 16px; left: 16px;
    font-size: 18px; font-weight: 600; opacity: 0.85;
    text-shadow: 0 1px 4px rgba(0,0,0,0.6); z-index: 10;
  }

  .slider-container {
    background: rgba(0,0,0,0.7); padding: 10px 14px 12px;
    border-radius: 8px; font-size: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    width: 100%; margin-top: 8px;
  }
  .slider-labels {
    display: flex; justify-content: space-between;
    margin-bottom: 4px;
  }
  .slider-labels span { opacity: 0.4; transition: opacity 0.3s; font-size: 11px; }
  .slider-labels span.active { opacity: 1.0; font-weight: 600; }
  .slider-labels-right {
    display: flex; justify-content: space-between;
    margin-top: 3px; color: #8cf;
  }
  .slider-labels-right span { opacity: 0.4; transition: opacity 0.3s; font-size: 11px; }
  .slider-labels-right span.active { opacity: 1.0; font-weight: 600; }
  .run-slider {
    width: 100%; cursor: pointer;
    accent-color: #6af;
  }

  /* Wrapper that holds legend + slider in top-right */
  .right-panel {
    position: absolute; top: 40px; right: 16px;
    max-width: 220px; z-index: 10;
  }

  #info {
    position: fixed; bottom: 16px; left: 16px;
    font-size: 12px; opacity: 0.4; z-index: 10;
  }
</style>
</head>
<body>

<div id="tooltip"></div>
<div id="info">Click point to pin text &middot; Esc to clear &middot; Drag to rotate &middot; Scroll to zoom</div>

<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.170.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.170.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PAYLOAD = __DATA_JSON__;

const NOISE_COLOR = '#555555';
const UNCOLORED = new THREE.Color('#7ab8f5');

function clusterColor(clusterId) {
  if (clusterId === -1) return NOISE_COLOR;
  const hue = (clusterId * 137.508) % 360;
  return `hsl(${hue}, 70%, 55%)`;
}

function lerp(a, b, t) { return a + (b - a) * t; }

function parseColor(str) {
  return new THREE.Color(str);
}

const PIN_COLORS = ['#f47', '#4bf', '#fb3', '#6f6', '#c7f', '#f90', '#3df', '#f6a', '#7ff', '#df5'];
let pinColorIdx = 0;

// Smooth ease-in-out for animation
function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

const TRANSITION_MS = 800; // animation duration in ms

// ─── VizPanel: encapsulates one 3D scatter plot ──────────────────────

class VizPanel {
  constructor(container, pointsData, runsData) {
    this.container = container;
    this.pointsData = pointsData;
    this.runsData = runsData;
    this.meshes = [];
    this.currentRun = 0;

    // Animation state
    this.animating = false;
    this.fromRun = 0;
    this.toRun = 0;
    this.animStartTime = 0;

    this._setup();
  }

  _setup() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x111111);

    // Camera
    this.camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 1000);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(devicePixelRatio);
    this.container.appendChild(this.renderer.domElement);

    // Controls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;

    // Compute global bounds across ALL runs for stable framing
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    let minZ = Infinity, maxZ = -Infinity;

    for (const pt of this.pointsData) {
      for (const pos of pt.positions) {
        if (!pos) continue;
        minX = Math.min(minX, pos.x); maxX = Math.max(maxX, pos.x);
        minY = Math.min(minY, pos.y); maxY = Math.max(maxY, pos.y);
        minZ = Math.min(minZ, pos.z); maxZ = Math.max(maxZ, pos.z);
      }
    }

    this.cx = (minX + maxX) / 2;
    this.cy = (minY + maxY) / 2;
    this.cz = (minZ + maxZ) / 2;
    this.span = Math.max(maxX - minX, maxY - minY, maxZ - minZ) || 1;

    // Geometry
    const sphereRadius = this.span * 0.018;
    const sphereGeo = new THREE.SphereGeometry(sphereRadius, 16, 12);

    // Create meshes for all points
    for (const pt of this.pointsData) {
      // Find position in run 0, or first available
      const initPos = pt.positions[0] || pt.positions.find(p => p !== null);
      const clusterId = initPos ? initPos.cluster : -1;
      const color = clusterColor(clusterId);

      const material = new THREE.MeshStandardMaterial({
        color: color,
        roughness: 0.5,
        metalness: 0.1,
        emissive: color,
        emissiveIntensity: 0.3,
        transparent: true,
        opacity: pt.positions[0] ? 1.0 : 0.0,
      });

      const mesh = new THREE.Mesh(sphereGeo, material);
      mesh.userData = { pointData: pt };

      if (initPos) {
        mesh.position.set(
          initPos.x - this.cx,
          initPos.y - this.cy,
          initPos.z - this.cz
        );
      }
      mesh.visible = !!pt.positions[0];

      this.scene.add(mesh);
      this.meshes.push(mesh);
    }

    // Lighting
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(this.span, this.span, this.span);
    this.scene.add(dirLight);

    // Camera position
    this.camera.position.set(
      this.span * 0.8, this.span * 0.6, this.span * 0.8
    );
    this.controls.target.set(0, 0, 0);
    this.controls.update();

    // Right panel (holds legend + slider)
    this.rightPanel = document.createElement('div');
    this.rightPanel.className = 'right-panel';
    this.container.appendChild(this.rightPanel);

    // Legend
    this.legendEl = document.createElement('div');
    this.legendEl.className = 'legend';
    this.rightPanel.appendChild(this.legendEl);
    this._updateLegend(0);

    // Clustering toggle
    this.clusteringVisible = true;
    const ctrlEl = document.createElement('div');
    ctrlEl.style.cssText = 'margin-top: 8px; font-size: 12px;';
    const ctrlLabel = document.createElement('label');
    ctrlLabel.style.cssText = 'display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;';
    const ctrlCheck = document.createElement('input');
    ctrlCheck.type = 'checkbox';
    ctrlCheck.checked = true;
    ctrlCheck.style.cursor = 'pointer';
    ctrlLabel.appendChild(ctrlCheck);
    ctrlLabel.append('Show Clustering');
    ctrlEl.appendChild(ctrlLabel);
    this.rightPanel.appendChild(ctrlEl);

    ctrlCheck.addEventListener('change', (e) => {
      this.clusteringVisible = e.target.checked;
      this.legendEl.style.display = this.clusteringVisible ? '' : 'none';
      this._recolorAll();
    });

    // Raycaster for hover
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    this.hoveredMesh = null;

    this.renderer.domElement.addEventListener('mousemove', (e) => {
      this._onMouseMove(e);
    });

    // Click-to-pin tooltips with connector lines
    this.pinnedTips = []; // each: { el, mesh, line, dot }
    this._mouseDownPos = null;

    // SVG for connector lines (scoped to this panel's container)
    this.pinLinesSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.pinLinesSvg.setAttribute('class', 'pin-lines');
    this.container.appendChild(this.pinLinesSvg);

    this.renderer.domElement.addEventListener('mousedown', (e) => {
      this._mouseDownPos = { x: e.clientX, y: e.clientY };
    });

    this.renderer.domElement.addEventListener('mouseup', (e) => {
      if (!this._mouseDownPos) return;
      const dx = e.clientX - this._mouseDownPos.x;
      const dy = e.clientY - this._mouseDownPos.y;
      if (dx * dx + dy * dy > 25) return;

      const canvasRect = this.renderer.domElement.getBoundingClientRect();
      this.mouse.x = ((e.clientX - canvasRect.left) / canvasRect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - canvasRect.top) / canvasRect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.mouse, this.camera);
      const visible = this.meshes.filter(m => m.visible && m.material.opacity > 0.1);
      const hits = this.raycaster.intersectObjects(visible);

      if (hits.length > 0) {
        const hitMesh = hits[0].object;
        const pt = hitMesh.userData.pointData;
        const pos = pt.positions[this.currentRun];
        const clusterId = pos ? pos.cluster : -1;
        const clusterLabel = clusterId === -1 ? 'Noise' : `Cluster ${clusterId}`;
        const tagColor = clusterColor(clusterId);

        const pinColor = PIN_COLORS[pinColorIdx % PIN_COLORS.length];
        pinColorIdx++;

        const el = document.createElement('div');
        el.className = 'pinned-tooltip';
        el.style.borderColor = pinColor;
        const pinTagHTML = this.clusteringVisible ? `<div class="cluster-tag" style="background:${tagColor}">${clusterLabel}</div><br>` : '';
        el.innerHTML = `<span class="pin-close">&times;</span>` + pinTagHTML + pt.text;
        el.style.left = (e.clientX + 16) + 'px';
        el.style.top = (e.clientY + 16) + 'px';
        document.body.appendChild(el);

        const pr = el.getBoundingClientRect();
        if (pr.right > innerWidth) el.style.left = (e.clientX - pr.width - 16) + 'px';
        if (pr.bottom > innerHeight) el.style.top = (e.clientY - pr.height - 16) + 'px';

        // Connector line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('stroke', pinColor);
        line.setAttribute('stroke-width', '1.5');
        line.setAttribute('stroke-opacity', '0.7');
        this.pinLinesSvg.appendChild(line);

        // Dot on the node
        const dot = document.createElement('div');
        dot.className = 'pin-dot';
        dot.style.borderColor = pinColor;
        dot.style.background = pinColor;
        document.body.appendChild(dot);

        // Paint the 3D mesh the pin color
        const origColor = hitMesh.material.color.clone();
        const origEmissive = hitMesh.material.emissive.clone();
        const meshPinColor = new THREE.Color(pinColor);
        hitMesh.material.color.copy(meshPinColor);
        hitMesh.material.emissive.copy(meshPinColor);

        const pinObj = { el, mesh: hitMesh, line, dot, origColor, origEmissive };

        el.querySelector('.pin-close').addEventListener('click', () => {
          el.remove(); line.remove(); dot.remove();
          hitMesh.material.color.copy(origColor);
          hitMesh.material.emissive.copy(origEmissive);
          const idx = this.pinnedTips.indexOf(pinObj);
          if (idx !== -1) this.pinnedTips.splice(idx, 1);
        });
        this.pinnedTips.push(pinObj);
      }
    });

    // Resize
    const ro = new ResizeObserver(() => this._onResize());
    ro.observe(this.container);
  }

  _onResize() {
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  _onMouseMove(e) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const visible = this.meshes.filter(m => m.visible && m.material.opacity > 0.1);
    const hits = this.raycaster.intersectObjects(visible);

    const tooltipEl = document.getElementById('tooltip');

    if (hits.length > 0) {
      const mesh = hits[0].object;
      if (this.hoveredMesh !== mesh) {
        if (this.hoveredMesh) {
          this.hoveredMesh.material.emissiveIntensity = 0.3;
          this.hoveredMesh.scale.setScalar(1);
        }
        this.hoveredMesh = mesh;
        mesh.material.emissiveIntensity = 0.8;
        mesh.scale.setScalar(1.4);
      }

      const pt = mesh.userData.pointData;
      const pos = pt.positions[this.currentRun];
      const clusterId = pos ? pos.cluster : -1;
      const clusterLabel = clusterId === -1 ? 'Noise' : `Cluster ${clusterId}`;
      const tagColor = clusterColor(clusterId);

      const tagHTML = this.clusteringVisible ? `<div class="cluster-tag" style="background:${tagColor}">${clusterLabel}</div><br>` : '';
      tooltipEl.innerHTML = tagHTML + pt.text;
      tooltipEl.style.display = 'block';
      tooltipEl.style.left = (e.clientX + 16) + 'px';
      tooltipEl.style.top = (e.clientY + 16) + 'px';

      const tr = tooltipEl.getBoundingClientRect();
      if (tr.right > innerWidth) tooltipEl.style.left = (e.clientX - tr.width - 16) + 'px';
      if (tr.bottom > innerHeight) tooltipEl.style.top = (e.clientY - tr.height - 16) + 'px';
    } else {
      if (this.hoveredMesh) {
        this.hoveredMesh.material.emissiveIntensity = 0.3;
        this.hoveredMesh.scale.setScalar(1);
        this.hoveredMesh = null;
      }
      tooltipEl.style.display = 'none';
    }
  }

  _updateLegend(runIndex) {
    const clusterCounts = {};
    for (const pt of this.pointsData) {
      const pos = pt.positions[runIndex];
      if (!pos) continue;
      const cid = pos.cluster;
      clusterCounts[cid] = (clusterCounts[cid] || 0) + 1;
    }

    const clusterIds = Object.keys(clusterCounts)
      .map(Number)
      .sort((a, b) => a - b);

    let html = '<h3>Clusters</h3>';
    for (const cid of clusterIds) {
      const label = cid === -1 ? 'Noise' : `Cluster ${cid}`;
      html += `<div class="legend-item">
        <div class="legend-swatch" style="background:${clusterColor(cid)}"></div>
        ${label} (${clusterCounts[cid]})
      </div>`;
    }
    this.legendEl.innerHTML = html;
  }

  // Trigger an animated transition to a new run index
  transitionTo(runIndex) {
    if (runIndex === this.currentRun && !this.animating) return;
    this.fromRun = this.currentRun;
    this.toRun = runIndex;
    this.animStartTime = performance.now();
    this.animating = true;
  }

  // Called every frame from the animation loop
  tick(now) {
    if (this.animating) {
      const elapsed = now - this.animStartTime;
      const rawT = Math.min(elapsed / TRANSITION_MS, 1.0);
      const t = easeInOutCubic(rawT);

      this._applyInterpolation(this.fromRun, this.toRun, t);

      if (rawT >= 1.0) {
        this.animating = false;
        this.currentRun = this.toRun;
        this._updateLegend(this.currentRun);
      }
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this._updatePinLines();
  }

  _projectToScreen(mesh) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    const v = mesh.position.clone().project(this.camera);
    return {
      x: (v.x * 0.5 + 0.5) * rect.width + rect.left,
      y: (-v.y * 0.5 + 0.5) * rect.height + rect.top,
    };
  }

  _updatePinLines() {
    for (const pin of this.pinnedTips) {
      const scr = this._projectToScreen(pin.mesh);
      pin.dot.style.left = scr.x + 'px';
      pin.dot.style.top = scr.y + 'px';
      const rect = pin.el.getBoundingClientRect();
      const tipCx = rect.left + rect.width / 2;
      const tipCy = rect.top + rect.height / 2;
      const dx = scr.x - tipCx, dy = scr.y - tipCy;
      let ex, ey;
      if (Math.abs(dx) / (rect.width / 2) > Math.abs(dy) / (rect.height / 2)) {
        const side = dx > 0 ? rect.left : rect.right;
        ex = side; ey = tipCy + dy * Math.abs((side - tipCx) / dx || 0);
      } else {
        const side = dy > 0 ? rect.top : rect.bottom;
        ey = side; ex = tipCx + dx * Math.abs((side - tipCy) / dy || 0);
      }
      pin.line.setAttribute('x1', scr.x);
      pin.line.setAttribute('y1', scr.y);
      pin.line.setAttribute('x2', ex);
      pin.line.setAttribute('y2', ey);
    }
  }

  _colorFor(clusterId) {
    if (!this.clusteringVisible) return UNCOLORED;
    return parseColor(clusterColor(clusterId));
  }

  _recolorAll() {
    for (let i = 0; i < this.meshes.length; i++) {
      const mesh = this.meshes[i];
      if (!mesh.visible) continue;
      const pos = this.pointsData[i].positions[this.currentRun];
      if (!pos) continue;
      const col = this._colorFor(pos.cluster);
      mesh.material.color.copy(col);
      mesh.material.emissive.copy(col);
      mesh.material.emissiveIntensity = this.clusteringVisible ? 0.3 : 0.4;
    }
  }

  _applyInterpolation(fromRun, toRun, t) {
    for (let i = 0; i < this.pointsData.length; i++) {
      const pt = this.pointsData[i];
      const posA = pt.positions[fromRun];
      const posB = pt.positions[toRun];
      const mesh = this.meshes[i];

      if (posA && posB) {
        mesh.position.set(
          lerp(posA.x, posB.x, t) - this.cx,
          lerp(posA.y, posB.y, t) - this.cy,
          lerp(posA.z, posB.z, t) - this.cz
        );
        mesh.material.opacity = 1.0;
        mesh.visible = true;

        const activePos = t < 0.5 ? posA : posB;
        const col = this._colorFor(activePos.cluster);
        mesh.material.color.copy(col);
        mesh.material.emissive.copy(col);
      } else if (posA && !posB) {
        mesh.position.set(posA.x - this.cx, posA.y - this.cy, posA.z - this.cz);
        mesh.material.opacity = 1.0 - t;
        mesh.visible = mesh.material.opacity > 0.01;
        const col = this._colorFor(posA.cluster);
        mesh.material.color.copy(col);
        mesh.material.emissive.copy(col);
      } else if (!posA && posB) {
        mesh.position.set(posB.x - this.cx, posB.y - this.cy, posB.z - this.cz);
        mesh.material.opacity = t;
        mesh.visible = mesh.material.opacity > 0.01;
        const col = this._colorFor(posB.cluster);
        mesh.material.color.copy(col);
        mesh.material.emissive.copy(col);
      } else {
        mesh.visible = false;
      }
    }
  }
}

// ─── Initialize based on mode ────────────────────────────────────────

const mode = PAYLOAD.mode;
const panels = [];

if (mode === 'single') {
  // Single-view mode
  const container = document.createElement('div');
  container.className = 'viz-container';
  document.body.insertBefore(container, document.getElementById('tooltip'));

  const labelEl = document.createElement('div');
  labelEl.id = 'run-label';
  container.appendChild(labelEl);

  const panel = new VizPanel(container, PAYLOAD.points, PAYLOAD.runs);
  panels.push({ panel, runs: PAYLOAD.runs, labelEl });

  labelEl.textContent = PAYLOAD.runs[0].label;

  buildSlider(PAYLOAD.runs.map(r => r.label), null);

} else {
  // Side-by-side mode
  const wrapper = document.createElement('div');
  wrapper.className = 'viz-container side-by-side';
  document.body.insertBefore(wrapper, document.getElementById('tooltip'));

  for (const sideKey of ['left', 'right']) {
    const sideData = PAYLOAD[sideKey];

    const panelEl = document.createElement('div');
    panelEl.className = 'viz-panel';
    wrapper.appendChild(panelEl);

    const titleEl = document.createElement('div');
    titleEl.className = 'panel-title';
    titleEl.textContent = sideData.title + ' \u2014 ' + sideData.runs[0].label;
    panelEl.appendChild(titleEl);

    const panel = new VizPanel(panelEl, sideData.points, sideData.runs);
    panels.push({ panel, runs: sideData.runs, labelEl: titleEl, sideKey });
  }

  const leftLabels = PAYLOAD.left.runs.map(r => r.label);
  const rightLabels = PAYLOAD.right.runs.map(r => r.label);
  buildSlider(leftLabels, rightLabels);
}

function buildSlider(topLabels, bottomLabels) {
  const sliderContainer = document.createElement('div');
  sliderContainer.className = 'slider-container';

  // Top labels
  const labelsTop = document.createElement('div');
  labelsTop.className = 'slider-labels';
  for (let i = 0; i < topLabels.length; i++) {
    const span = document.createElement('span');
    span.textContent = topLabels[i];
    span.className = i === 0 ? 'active' : '';
    labelsTop.appendChild(span);
  }
  sliderContainer.appendChild(labelsTop);

  // Slider — discrete integer steps
  const slider = document.createElement('input');
  slider.className = 'run-slider';
  slider.type = 'range';
  slider.min = '0';
  slider.max = String(topLabels.length - 1);
  slider.step = '1';
  slider.value = '0';
  sliderContainer.appendChild(slider);

  // Bottom labels (side-by-side only)
  if (bottomLabels) {
    const labelsBottom = document.createElement('div');
    labelsBottom.className = 'slider-labels-right';
    for (let i = 0; i < bottomLabels.length; i++) {
      const span = document.createElement('span');
      span.textContent = bottomLabels[i];
      span.className = i === 0 ? 'active' : '';
      labelsBottom.appendChild(span);
    }
    sliderContainer.appendChild(labelsBottom);
  }

  // Append slider to each panel's right-panel (below legend)
  // For single mode there's one panel; for side-by-side, clone into each
  if (panels.length === 1) {
    panels[0].panel.rightPanel.appendChild(sliderContainer);
  } else {
    for (let pi = 0; pi < panels.length; pi++) {
      const clone = pi === 0 ? sliderContainer : sliderContainer.cloneNode(true);
      panels[pi].panel.rightPanel.appendChild(clone);
    }
  }

  // Wire up all slider instances together
  const allSliders = document.querySelectorAll('.run-slider');
  for (const sl of allSliders) {
    sl.addEventListener('input', () => {
      const targetRun = parseInt(sl.value, 10);

      // Sync all sliders
      for (const other of allSliders) {
        if (other !== sl) other.value = sl.value;
      }

      // Highlight active labels in all slider containers
      document.querySelectorAll('.slider-labels').forEach(container => {
        container.querySelectorAll('span').forEach((s, i) =>
          s.className = i === targetRun ? 'active' : ''
        );
      });
      document.querySelectorAll('.slider-labels-right').forEach(container => {
        container.querySelectorAll('span').forEach((s, i) =>
          s.className = i === targetRun ? 'active' : ''
        );
      });

      for (const { panel, runs, labelEl, sideKey } of panels) {
        const clampedTarget = Math.min(targetRun, runs.length - 1);
        panel.transitionTo(clampedTarget);

        if (PAYLOAD.mode === 'single') {
          labelEl.textContent = runs[clampedTarget].label;
        } else {
          labelEl.textContent = PAYLOAD[sideKey].title + ' \u2014 ' + runs[clampedTarget].label;
        }
      }
    });
  }
}

// Escape clears all pinned tooltips
addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    for (const { panel } of panels) {
      for (const pin of panel.pinnedTips) {
        pin.el.remove(); pin.line.remove(); pin.dot.remove();
        pin.mesh.material.color.copy(pin.origColor);
        pin.mesh.material.emissive.copy(pin.origEmissive);
      }
      panel.pinnedTips.length = 0;
    }
  }
});

// Animation loop — drives time-based transitions
function animate(now) {
  requestAnimationFrame(animate);
  for (const { panel } of panels) {
    panel.tick(now);
  }
}
requestAnimationFrame(animate);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
