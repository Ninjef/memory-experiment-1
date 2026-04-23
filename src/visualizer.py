"""Generate a self-contained HTML file for 3D cluster visualization."""

from __future__ import annotations

import json
from pathlib import Path

from src.pipeline import PipelineResult


def generate_viz_html(
    result: PipelineResult,
    output_path: Path,
    viz_coords: dict[str, tuple[float, float, float]] | None = None,
    title: str = "Cluster Visualization",
    run_config: dict | None = None,
    presets: dict | None = None,
) -> None:
    """Write a standalone HTML file with an interactive 3D scatter plot.

    Args:
        result: Pipeline result (used for cluster/text lookups).
        output_path: Where to write the HTML file.
        viz_coords: Coordinate dict to visualize. Defaults to result.viz_coords.
        title: Page title shown in the browser tab and header.
        run_config: Pipeline configuration dict to display in the UI.
        presets: Optional preset config (pins, camera, toggles) to apply on load.
    """
    if viz_coords is None:
        viz_coords = result.viz_coords

    # Build data payload — memory points
    id_to_cluster: dict[str, int] = {}
    id_to_text: dict[str, str] = {}
    for cluster_id, chunks in result.clusters.items():
        for chunk in chunks:
            id_to_cluster[chunk.id] = cluster_id
            id_to_text[chunk.id] = chunk.text

    points = []
    for chunk_id, (x, y, z) in viz_coords.items():
        points.append({
            "id": chunk_id,
            "cluster": id_to_cluster.get(chunk_id, -1),
            "x": round(x, 5),
            "y": round(y, 5),
            "z": round(z, 5),
            "text": id_to_text.get(chunk_id, "")[:200],
            "type": "memory",
        })

    # Build insight points at cluster centroids
    if result.insights and viz_coords:
        # Compute centroid per cluster from viz_coords
        cluster_coords: dict[int, list[tuple[float, float, float]]] = {}
        for chunk_id, (x, y, z) in viz_coords.items():
            cid = id_to_cluster.get(chunk_id, -1)
            if cid != -1:
                cluster_coords.setdefault(cid, []).append((x, y, z))

        centroids: dict[int, tuple[float, float, float]] = {}
        for cid, coords in cluster_coords.items():
            n = len(coords)
            centroids[cid] = (
                sum(c[0] for c in coords) / n,
                sum(c[1] for c in coords) / n,
                sum(c[2] for c in coords) / n,
            )

        # Group insights by cluster_id
        insights_by_cluster: dict[int, list] = {}
        for insight in result.insights:
            cid = insight.metadata.get("cluster_id")
            if cid is not None and cid in centroids:
                insights_by_cluster.setdefault(cid, []).append(insight)

        # Compute a small offset scale based on data bounds
        all_x = [p["x"] for p in points]
        all_y = [p["y"] for p in points]
        all_z = [p["z"] for p in points]
        span = max(
            (max(all_x) - min(all_x)) if all_x else 1,
            (max(all_y) - min(all_y)) if all_y else 1,
            (max(all_z) - min(all_z)) if all_z else 1,
        ) or 1
        offset_step = span * 0.04

        for cid, insights in insights_by_cluster.items():
            cx, cy, cz = centroids[cid]
            for idx, insight in enumerate(insights):
                # Offset along y-axis to avoid overlap
                offset = idx * offset_step
                tooltip_parts = [insight.text[:200]]
                if insight.metadata.get("confidence") is not None:
                    tooltip_parts.append(
                        f"Confidence: {insight.metadata['confidence']}"
                    )
                if insight.metadata.get("suggestedAction"):
                    tooltip_parts.append(
                        f"Action: {insight.metadata['suggestedAction']}"
                    )
                points.append({
                    "id": insight.id,
                    "cluster": cid,
                    "x": round(cx, 5),
                    "y": round(cy + offset, 5),
                    "z": round(cz, 5),
                    "text": " | ".join(tooltip_parts),
                    "type": "insight",
                })

    data_json = json.dumps(points)
    config_json = json.dumps(run_config or {})
    presets_json = json.dumps(presets) if presets else "null"

    html = _HTML_TEMPLATE.replace("__DATA_JSON__", data_json).replace(
        "__TITLE__", title
    ).replace("__CONFIG_JSON__", config_json).replace(
        "__PRESETS_JSON__", presets_json
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #111; color: #eee; font-family: system-ui, sans-serif; overflow: hidden; }
  canvas { display: block; }
  #tooltip {
    position: absolute; pointer-events: none; display: none;
    background: rgba(0,0,0,0.85); color: #fff; padding: 10px 14px;
    border-radius: 6px; font-size: 13px; max-width: 360px;
    line-height: 1.4; border: 1px solid rgba(255,255,255,0.15);
  }
  #tooltip .cluster-tag {
    display: inline-block; padding: 2px 8px; border-radius: 3px;
    font-size: 11px; font-weight: 600; margin-bottom: 6px;
  }
  .pinned-tooltip {
    position: absolute; pointer-events: auto;
    background: rgba(0,0,0,0.9); color: #fff;
    padding: 0.75em 1em; border-radius: 0.45em;
    font-size: max(0.9vw, 10px); max-width: 25vw;
    line-height: 1.4; border: 1px solid rgba(255,255,255,0.3);
    z-index: 90; cursor: grab; user-select: none;
  }
  .pinned-tooltip.dragging { cursor: grabbing; }
  .pinned-tooltip .cluster-tag {
    display: inline-block; padding: 0.15em 0.6em; border-radius: 0.2em;
    font-size: 0.85em; font-weight: 600; margin-bottom: 0.45em;
  }
  .pinned-tooltip .pin-close {
    position: absolute; top: 0.3em; right: 0.6em;
    cursor: pointer; opacity: 0.5; font-size: 1.05em;
  }
  .pinned-tooltip .pin-close:hover { opacity: 1; }
  #pin-lines {
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 89;
  }
  .pin-dot {
    position: absolute; width: max(0.55vw, 6px); height: max(0.55vw, 6px);
    border-radius: 50%; border: max(0.14vw, 1.5px) solid rgba(255,255,255,0.8);
    pointer-events: none; z-index: 91;
    transform: translate(-50%, -50%);
  }
  #legend {
    position: absolute; top: 16px; right: 16px;
    background: rgba(0,0,0,0.7); padding: 14px 18px;
    border-radius: 8px; font-size: 13px;
    border: 1px solid rgba(255,255,255,0.1);
    max-height: 80vh; overflow-y: auto;
  }
  #legend h3 { margin-bottom: 8px; font-size: 14px; }
  .legend-item { display: flex; align-items: center; margin: 4px 0; }
  .legend-swatch {
    width: 12px; height: 12px; border-radius: 50%;
    margin-right: 8px; flex-shrink: 0;
  }
  .legend-swatch.diamond {
    border-radius: 0; transform: rotate(45deg);
    width: 10px; height: 10px;
  }
  #controls {
    position: absolute; bottom: 16px; right: 16px;
    background: rgba(0,0,0,0.7); padding: 10px 14px;
    border-radius: 8px; font-size: 13px;
    border: 1px solid rgba(255,255,255,0.1);
  }
  #controls label {
    display: flex; align-items: center; gap: 6px; cursor: pointer;
    user-select: none;
  }
  #controls input[type="checkbox"] { cursor: pointer; }
  #copy-preset {
    display: block; margin-top: 8px; padding: 6px 12px;
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
    color: #eee; border-radius: 4px; cursor: pointer; font-size: 12px;
    width: 100%;
  }
  #copy-preset:hover { background: rgba(255,255,255,0.2); }
  #copy-preset.copied { background: rgba(100,200,100,0.3); border-color: rgba(100,200,100,0.5); }
  #info {
    position: absolute; bottom: 16px; left: 16px;
    font-size: 12px; opacity: 0.5;
  }
  #run-name {
    position: absolute; top: 16px; left: 16px;
    font-size: 18px; font-weight: 600; opacity: 0.85;
    text-shadow: 0 1px 4px rgba(0,0,0,0.6);
  }
  #config-panel {
    position: absolute; top: 50px; left: 16px;
    background: rgba(0,0,0,0.7); padding: 14px 18px;
    border-radius: 8px; font-size: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    max-width: 320px; max-height: 60vh; overflow-y: auto;
  }
  #config-panel h3 {
    margin-bottom: 8px; font-size: 13px; font-weight: 600;
    opacity: 0.9;
  }
  #config-panel table { border-collapse: collapse; width: 100%; }
  #config-panel td {
    padding: 3px 0; vertical-align: top; line-height: 1.4;
  }
  #config-panel td.cfg-key {
    color: rgba(255,255,255,0.5); padding-right: 12px; white-space: nowrap;
  }
  #config-panel td.cfg-val {
    color: rgba(255,255,255,0.85); word-break: break-word;
  }
  #config-panel .cfg-section {
    margin-top: 8px; padding-top: 6px;
    border-top: 1px solid rgba(255,255,255,0.1);
    font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.5);
    text-transform: uppercase; letter-spacing: 0.5px;
  }
</style>
</head>
<body>
<div id="run-name">__TITLE__</div>
<div id="config-panel"></div>
<div id="tooltip"></div>
<svg id="pin-lines"></svg>
<div id="legend"></div>
<div id="controls"></div>
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

const DATA = __DATA_JSON__;
const CONFIG = __CONFIG_JSON__;
const PRESETS = __PRESETS_JSON__;

// Build config panel
{
  const panel = document.getElementById('config-panel');
  const entries = Object.entries(CONFIG);
  if (entries.length > 0) {
    let html = '<h3>Configuration</h3><table>';
    for (const [key, value] of entries) {
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        html += `<tr><td colspan="2" class="cfg-section">${key.replace(/_/g, ' ')}</td></tr>`;
        for (const [sk, sv] of Object.entries(value)) {
          const display = sv === null ? 'none' : Array.isArray(sv) ? sv.join(', ') : sv;
          html += `<tr><td class="cfg-key">${sk.replace(/_/g, ' ')}</td><td class="cfg-val">${display}</td></tr>`;
        }
      } else {
        const display = value === null ? 'none' : Array.isArray(value) ? value.join(', ') : value;
        html += `<tr><td class="cfg-key">${key.replace(/_/g, ' ')}</td><td class="cfg-val">${display}</td></tr>`;
      }
    }
    html += '</table>';
    panel.innerHTML = html;
  }
}

const hasInsights = DATA.some(p => p.type === 'insight');

// Color — golden-angle HSL for unlimited distinct colors, noise is gray
const NOISE_COLOR = '#555555';

function clusterColor(clusterId) {
  if (clusterId === -1) return NOISE_COLOR;
  const hue = (clusterId * 137.508) % 360;
  return `hsl(${hue}, 70%, 55%)`;
}

// Setup scene
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// Compute data bounds for camera positioning
let minX = Infinity, maxX = -Infinity;
let minY = Infinity, maxY = -Infinity;
let minZ = Infinity, maxZ = -Infinity;
for (const p of DATA) {
  minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
  minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
  minZ = Math.min(minZ, p.z); maxZ = Math.max(maxZ, p.z);
}
const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2, cz = (minZ + maxZ) / 2;
const span = Math.max(maxX - minX, maxY - minY, maxZ - minZ) || 1;

// Geometries
const SPHERE_RADIUS = span * 0.018;
const sphereGeo = new THREE.SphereGeometry(SPHERE_RADIUS, 16, 12);
const insightGeo = new THREE.OctahedronGeometry(SPHERE_RADIUS * 2.0);

const memoryMeshes = [];
const insightMeshes = [];

for (const p of DATA) {
  const color = clusterColor(p.cluster);
  const isInsight = p.type === 'insight';

  const material = new THREE.MeshStandardMaterial({
    color: isInsight ? '#ffffff' : color,
    roughness: isInsight ? 0.3 : 0.5,
    metalness: isInsight ? 0.2 : 0.1,
    emissive: color,
    emissiveIntensity: isInsight ? 0.6 : 0.3,
  });

  const mesh = new THREE.Mesh(isInsight ? insightGeo : sphereGeo, material);
  mesh.position.set(p.x - cx, p.y - cy, p.z - cz);
  mesh.userData = p;
  scene.add(mesh);

  if (isInsight) {
    insightMeshes.push(mesh);
  } else {
    memoryMeshes.push(mesh);
  }
}

// Lighting
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(span, span, span);
scene.add(dirLight);

// Camera
camera.position.set(span * 0.8, span * 0.6, span * 0.8);
controls.target.set(0, 0, 0);
controls.update();

// Legend
const clusterIds = [...new Set(DATA.map(p => p.cluster))].sort((a, b) => a - b);
const legendEl = document.getElementById('legend');
let legendHTML = '<h3>Clusters</h3>';
for (const cid of clusterIds) {
  const label = cid === -1 ? 'Noise' : `Cluster ${cid}`;
  const count = DATA.filter(p => p.cluster === cid && p.type !== 'insight').length;
  legendHTML += `<div class="legend-item">
    <div class="legend-swatch" style="background:${clusterColor(cid)}"></div>
    ${label} (${count})
  </div>`;
}
if (hasInsights) {
  const insightCount = DATA.filter(p => p.type === 'insight').length;
  legendHTML += `<div class="legend-item" style="margin-top:8px; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px;">
    <div class="legend-swatch diamond" style="background:#d4a017"></div>
    Insights (${insightCount})
  </div>`;
}
legendEl.innerHTML = legendHTML;

// Controls
const controlsEl = document.getElementById('controls');
const UNCOLORED = new THREE.Color('#7ab8f5');
let clusteringVisible = true;

let controlsHTML = '<label><input type="checkbox" id="toggleClustering" checked> Show Clustering</label>';
if (hasInsights) {
  controlsHTML += '<label style="margin-top:4px"><input type="checkbox" id="toggleInsights" checked> Show Insights</label>';
}
controlsHTML += '<button id="copy-preset">Copy Preset JSON</button>';
controlsEl.innerHTML = controlsHTML;

function applyClusterColors() {
  if (clusteringVisible) {
    for (const m of memoryMeshes) {
      const col = new THREE.Color(clusterColor(m.userData.cluster));
      m.material.color.copy(col);
      m.material.emissive.copy(col);
      m.material.emissiveIntensity = 0.3;
    }
    legendEl.style.display = '';
  } else {
    for (const m of memoryMeshes) {
      m.material.color.copy(UNCOLORED);
      m.material.emissive.copy(UNCOLORED);
      m.material.emissiveIntensity = 0.4;
    }
    legendEl.style.display = 'none';
  }
}

document.getElementById('toggleClustering').addEventListener('change', (e) => {
  clusteringVisible = e.target.checked;
  applyClusterColors();
});

if (hasInsights) {
  document.getElementById('toggleInsights').addEventListener('change', (e) => {
    const visible = e.target.checked;
    for (const m of insightMeshes) {
      m.visible = visible;
    }
  });
}

// Raycaster for hover tooltips
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const tooltipEl = document.getElementById('tooltip');
let hoveredMesh = null;

function getAllVisibleMeshes() {
  return [...memoryMeshes, ...insightMeshes.filter(m => m.visible)];
}

renderer.domElement.addEventListener('mousemove', (e) => {
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(getAllVisibleMeshes());

  if (hits.length > 0) {
    const mesh = hits[0].object;
    if (hoveredMesh !== mesh) {
      // Reset previous
      if (hoveredMesh) {
        hoveredMesh.material.emissiveIntensity = hoveredMesh.userData.type === 'insight' ? 0.6 : 0.3;
        hoveredMesh.scale.setScalar(1);
      }
      hoveredMesh = mesh;
      mesh.material.emissiveIntensity = 0.8;
      mesh.scale.setScalar(1.4);
    }
    const p = mesh.userData;
    const isInsight = p.type === 'insight';
    const clusterLabel = p.cluster === -1 ? 'Noise' : `Cluster ${p.cluster}`;
    const tagColor = isInsight ? '#d4a017' : clusterColor(p.cluster);
    const tagLabel = isInsight ? `Insight (${clusterLabel})` : clusterLabel;
    const tagHTML = clusteringVisible ? `<div class="cluster-tag" style="background:${tagColor}">${tagLabel}</div><br>` : '';
    tooltipEl.innerHTML = tagHTML + p.text;
    tooltipEl.style.display = 'block';
    tooltipEl.style.left = (e.clientX + 16) + 'px';
    tooltipEl.style.top = (e.clientY + 16) + 'px';
    // Keep tooltip in viewport
    const rect = tooltipEl.getBoundingClientRect();
    if (rect.right > innerWidth) tooltipEl.style.left = (e.clientX - rect.width - 16) + 'px';
    if (rect.bottom > innerHeight) tooltipEl.style.top = (e.clientY - rect.height - 16) + 'px';
  } else {
    if (hoveredMesh) {
      hoveredMesh.material.emissiveIntensity = hoveredMesh.userData.type === 'insight' ? 0.6 : 0.3;
      hoveredMesh.scale.setScalar(1);
      hoveredMesh = null;
    }
    tooltipEl.style.display = 'none';
  }
});

// Click-to-pin tooltips with connector lines
const pinnedTips = []; // each: { el, mesh, line, dot }
const pinLinesSvg = document.getElementById('pin-lines');
let mouseDownPos = null;
const PIN_COLORS = ['#f47', '#4bf', '#fb3', '#6f6', '#c7f', '#f90', '#3df', '#f6a', '#7ff', '#df5'];
let pinColorIdx = 0;

function projectToScreen(mesh) {
  const v = mesh.position.clone().project(camera);
  return {
    x: (v.x * 0.5 + 0.5) * innerWidth,
    y: (-v.y * 0.5 + 0.5) * innerHeight,
  };
}

function updatePinLines() {
  for (const pin of pinnedTips) {
    const scr = projectToScreen(pin.mesh);
    // Update dot position
    pin.dot.style.left = scr.x + 'px';
    pin.dot.style.top = scr.y + 'px';
    // Reposition tooltip relative to projected point (offset is viewport fraction)
    pin.el.style.left = (scr.x + pin.pinOffset.x * innerWidth) + 'px';
    pin.el.style.top = (scr.y + pin.pinOffset.y * innerHeight) + 'px';
    // Update line: from dot to nearest edge of tooltip
    const rect = pin.el.getBoundingClientRect();
    const tipCx = rect.left + rect.width / 2;
    const tipCy = rect.top + rect.height / 2;
    // Clamp to tooltip edge
    const dx = scr.x - tipCx, dy = scr.y - tipCy;
    const absDx = Math.abs(dx), absDy = Math.abs(dy);
    let ex, ey;
    if (absDx / (rect.width / 2) > absDy / (rect.height / 2)) {
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

function createPin(hitMesh, pinColor, pinOffset) {
  const p = hitMesh.userData;
  const isInsight = p.type === 'insight';
  const clusterLabel = p.cluster === -1 ? 'Noise' : `Cluster ${p.cluster}`;
  const tagColor = isInsight ? '#d4a017' : clusterColor(p.cluster);
  const tagLabel = isInsight ? `Insight (${clusterLabel})` : clusterLabel;

  const el = document.createElement('div');
  el.className = 'pinned-tooltip';
  el.style.borderColor = pinColor;
  const pinTagHTML = clusteringVisible ? `<div class="cluster-tag" style="background:${tagColor}">${tagLabel}</div><br>` : '';
  el.innerHTML = `<span class="pin-close">&times;</span>` + pinTagHTML + p.text;

  const scr = projectToScreen(hitMesh);
  el.style.left = (scr.x + pinOffset.x * innerWidth) + 'px';
  el.style.top = (scr.y + pinOffset.y * innerHeight) + 'px';
  document.body.appendChild(el);

  // Connector line
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('stroke', pinColor);
  line.setAttribute('stroke-width', '1.5');
  line.setAttribute('stroke-opacity', '0.7');
  pinLinesSvg.appendChild(line);

  // Dot on the node
  const dot = document.createElement('div');
  dot.className = 'pin-dot';
  dot.style.borderColor = pinColor;
  dot.style.background = pinColor;
  document.body.appendChild(dot);

  // Paint the 3D mesh the pin color (save originals to restore on close)
  const origColor = hitMesh.material.color.clone();
  const origEmissive = hitMesh.material.emissive.clone();
  const meshPinColor = new THREE.Color(pinColor);
  hitMesh.material.color.copy(meshPinColor);
  hitMesh.material.emissive.copy(meshPinColor);

  const pinObj = { el, mesh: hitMesh, line, dot, origColor, origEmissive, pinOffset };

  // Drag support
  let dragStart = null;
  el.addEventListener('mousedown', (ev) => {
    if (ev.target.closest('.pin-close')) return;
    ev.preventDefault(); ev.stopPropagation();
    dragStart = { mx: ev.clientX, my: ev.clientY, ox: pinOffset.x, oy: pinOffset.y };
    el.classList.add('dragging');
    const onMove = (me) => {
      pinOffset.x = dragStart.ox + (me.clientX - dragStart.mx) / innerWidth;
      pinOffset.y = dragStart.oy + (me.clientY - dragStart.my) / innerHeight;
    };
    const onUp = () => {
      dragStart = null;
      el.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  el.querySelector('.pin-close').addEventListener('click', () => {
    el.remove(); line.remove(); dot.remove();
    hitMesh.material.color.copy(origColor);
    hitMesh.material.emissive.copy(origEmissive);
    const idx = pinnedTips.indexOf(pinObj);
    if (idx !== -1) pinnedTips.splice(idx, 1);
  });
  pinnedTips.push(pinObj);
}

renderer.domElement.addEventListener('mousedown', (e) => {
  mouseDownPos = { x: e.clientX, y: e.clientY };
});

renderer.domElement.addEventListener('mouseup', (e) => {
  if (!mouseDownPos) return;
  const dx = e.clientX - mouseDownPos.x;
  const dy = e.clientY - mouseDownPos.y;
  if (dx * dx + dy * dy > 25) return;

  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(getAllVisibleMeshes());

  if (hits.length > 0) {
    const hitMesh = hits[0].object;
    const scr = projectToScreen(hitMesh);
    const pinOffset = { x: (e.clientX - scr.x + 16) / innerWidth, y: (e.clientY - scr.y + 16) / innerHeight };
    const pinColor = PIN_COLORS[pinColorIdx % PIN_COLORS.length];
    pinColorIdx++;
    createPin(hitMesh, pinColor, pinOffset);
  }
});

addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    for (const pin of pinnedTips) {
      pin.el.remove(); pin.line.remove(); pin.dot.remove();
      pin.mesh.material.color.copy(pin.origColor);
      pin.mesh.material.emissive.copy(pin.origEmissive);
    }
    pinnedTips.length = 0;
  }
});

// Resize
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// Copy Preset JSON
document.getElementById('copy-preset').addEventListener('click', () => {
  const preset = {
    pins: pinnedTips.map(pin => ({
      pointId: pin.mesh.userData.id,
      color: pin.el.style.borderColor,
      offset: { x: +pin.pinOffset.x.toFixed(4), y: +pin.pinOffset.y.toFixed(4) },
    })),
    camera: {
      position: { x: +camera.position.x.toFixed(4), y: +camera.position.y.toFixed(4), z: +camera.position.z.toFixed(4) },
      target: { x: +controls.target.x.toFixed(4), y: +controls.target.y.toFixed(4), z: +controls.target.z.toFixed(4) },
    },
    clustering: clusteringVisible,
    insights: hasInsights ? (document.getElementById('toggleInsights')?.checked ?? true) : undefined,
  };
  navigator.clipboard.writeText(JSON.stringify(preset, null, 2)).then(() => {
    const btn = document.getElementById('copy-preset');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy Preset JSON'; btn.classList.remove('copied'); }, 2000);
  });
});

// Apply presets on load
function applyPresets() {
  if (!PRESETS) return;

  // 1. Toggle states
  if (PRESETS.clustering === false) {
    clusteringVisible = false;
    document.getElementById('toggleClustering').checked = false;
    applyClusterColors();
  }
  if (hasInsights && PRESETS.insights === false) {
    const cb = document.getElementById('toggleInsights');
    if (cb) {
      cb.checked = false;
      for (const m of insightMeshes) m.visible = false;
    }
  }

  // 2. Camera
  if (PRESETS.camera) {
    const cp = PRESETS.camera.position;
    const ct = PRESETS.camera.target;
    if (cp) camera.position.set(cp.x, cp.y, cp.z);
    if (ct) controls.target.set(ct.x, ct.y, ct.z);
    controls.update();
  }

  // 3. UI visibility
  if (PRESETS.ui) {
    const hide = (id) => { const el = document.getElementById(id); if (el) el.style.display = 'none'; };
    if (PRESETS.ui.config === false) hide('config-panel');
    if (PRESETS.ui.controls === false) hide('controls');
    if (PRESETS.ui.legend === false) hide('legend');
    if (PRESETS.ui.info === false) hide('info');
    if (PRESETS.ui.title === false) hide('run-name');
  }

  // 4. Pinned tooltips
  if (PRESETS.pins && PRESETS.pins.length > 0) {
    const idToMesh = {};
    for (const m of [...memoryMeshes, ...insightMeshes]) {
      idToMesh[m.userData.id] = m;
    }
    for (const pinDef of PRESETS.pins) {
      const hitMesh = idToMesh[pinDef.pointId];
      if (!hitMesh) continue;
      const pinColor = pinDef.color || PIN_COLORS[pinColorIdx % PIN_COLORS.length];
      pinColorIdx++;
      const raw = pinDef.offset || { x: 0.015, y: -0.02 };
      // Auto-detect old pixel offsets (abs > 2) vs new viewport fractions
      const pinOffset = (Math.abs(raw.x) > 2 || Math.abs(raw.y) > 2)
        ? { x: raw.x / innerWidth, y: raw.y / innerHeight }
        : { x: raw.x, y: raw.y };
      createPin(hitMesh, pinColor, pinOffset);
    }
  }
}
applyPresets();

// Animate
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
  updatePinLines();
}
animate();
</script>
</body>
</html>
"""
