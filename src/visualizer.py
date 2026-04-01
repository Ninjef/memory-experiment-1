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
) -> None:
    """Write a standalone HTML file with an interactive 3D scatter plot.

    Args:
        result: Pipeline result (used for cluster/text lookups).
        output_path: Where to write the HTML file.
        viz_coords: Coordinate dict to visualize. Defaults to result.viz_coords.
        title: Page title shown in the browser tab and header.
    """
    if viz_coords is None:
        viz_coords = result.viz_coords

    # Build data payload
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
        })

    data_json = json.dumps(points)

    html = _HTML_TEMPLATE.replace("__DATA_JSON__", data_json).replace(
        "__TITLE__", title
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
  #legend {
    position: absolute; top: 16px; right: 16px;
    background: rgba(0,0,0,0.7); padding: 14px 18px;
    border-radius: 8px; font-size: 13px;
    border: 1px solid rgba(255,255,255,0.1);
  }
  #legend h3 { margin-bottom: 8px; font-size: 14px; }
  .legend-item { display: flex; align-items: center; margin: 4px 0; }
  .legend-swatch {
    width: 12px; height: 12px; border-radius: 50%;
    margin-right: 8px; flex-shrink: 0;
  }
  #info {
    position: absolute; bottom: 16px; left: 16px;
    font-size: 12px; opacity: 0.5;
  }
</style>
</head>
<body>
<div id="tooltip"></div>
<div id="legend"></div>
<div id="info">Click + drag to rotate &middot; Scroll to zoom &middot; Right-click drag to pan</div>

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

// Color palette — distinct hues, noise is gray
const PALETTE = [
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
  '#86bcb6', '#8cd17d', '#b6992d', '#499894', '#d37295',
];
const NOISE_COLOR = '#555555';

function clusterColor(clusterId) {
  if (clusterId === -1) return NOISE_COLOR;
  return PALETTE[clusterId % PALETTE.length];
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

// Create points as spheres
const SPHERE_RADIUS = span * 0.018;
const geometry = new THREE.SphereGeometry(SPHERE_RADIUS, 16, 12);
const meshes = [];

for (const p of DATA) {
  const color = clusterColor(p.cluster);
  const material = new THREE.MeshStandardMaterial({
    color: color,
    roughness: 0.5,
    metalness: 0.1,
    emissive: color,
    emissiveIntensity: 0.3,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.set(p.x - cx, p.y - cy, p.z - cz);
  mesh.userData = p;
  scene.add(mesh);
  meshes.push(mesh);
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
  const count = DATA.filter(p => p.cluster === cid).length;
  legendHTML += `<div class="legend-item">
    <div class="legend-swatch" style="background:${clusterColor(cid)}"></div>
    ${label} (${count})
  </div>`;
}
legendEl.innerHTML = legendHTML;

// Raycaster for hover tooltips
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const tooltipEl = document.getElementById('tooltip');
let hoveredMesh = null;

renderer.domElement.addEventListener('mousemove', (e) => {
  mouse.x = (e.clientX / innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(meshes);

  if (hits.length > 0) {
    const mesh = hits[0].object;
    if (hoveredMesh !== mesh) {
      // Reset previous
      if (hoveredMesh) {
        hoveredMesh.material.emissiveIntensity = 0.3;
        hoveredMesh.scale.setScalar(1);
      }
      hoveredMesh = mesh;
      mesh.material.emissiveIntensity = 0.8;
      mesh.scale.setScalar(1.4);
    }
    const p = mesh.userData;
    const clusterLabel = p.cluster === -1 ? 'Noise' : `Cluster ${p.cluster}`;
    const color = clusterColor(p.cluster);
    tooltipEl.innerHTML = `<div class="cluster-tag" style="background:${color}">${clusterLabel}</div><br>${p.text}`;
    tooltipEl.style.display = 'block';
    tooltipEl.style.left = (e.clientX + 16) + 'px';
    tooltipEl.style.top = (e.clientY + 16) + 'px';
    // Keep tooltip in viewport
    const rect = tooltipEl.getBoundingClientRect();
    if (rect.right > innerWidth) tooltipEl.style.left = (e.clientX - rect.width - 16) + 'px';
    if (rect.bottom > innerHeight) tooltipEl.style.top = (e.clientY - rect.height - 16) + 'px';
  } else {
    if (hoveredMesh) {
      hoveredMesh.material.emissiveIntensity = 0.3;
      hoveredMesh.scale.setScalar(1);
      hoveredMesh = null;
    }
    tooltipEl.style.display = 'none';
  }
});

// Resize
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

// Animate
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
</script>
</body>
</html>
"""
