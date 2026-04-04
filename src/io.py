from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import MemoryChunk
from src.pipeline import PipelineResult
from src.visualizer import generate_viz_html


def load_chunks(path: str | Path) -> list[MemoryChunk]:
    """Read a JSONL file into a list of MemoryChunks."""
    chunks: list[MemoryChunk] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if "text" not in data:
                raise ValueError(f"Line {line_num}: missing required 'text' field")
            chunks.append(MemoryChunk.from_dict(data))
    return chunks


def save_chunks(chunks: list[MemoryChunk], path: str | Path) -> None:
    """Write MemoryChunks to a JSONL file (embeddings stripped)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_dict(include_embedding=False)) + "\n")


def save_run(
    result: PipelineResult,
    run_dir: Path,
    run_config: dict[str, Any],
) -> None:
    """Save a complete pipeline run to a folder with human-readable files."""
    run_dir.mkdir(parents=True, exist_ok=True)

    _save_insights(result, run_dir / "insights.json")
    _save_clusters(result, run_dir / "clusters.json")
    _save_cluster_texts_md(result, run_dir / "cluster_texts.md")
    _save_run_stats(result, run_dir / "run_info.json", run_config)

    if result.viz_coords:
        run_name = run_dir.name
        _save_viz_coords(result, run_dir / "viz_coords.csv")
        if result.viz_coords_original:
            # Steered space: what clustering actually saw
            generate_viz_html(
                result, run_dir / "viz_steered.html",
                viz_coords=result.viz_coords,
                title=f"{run_name} — Steered Embedding Space",
                run_config=run_config,
            )
            _save_viz_coords(
                result, run_dir / "viz_coords_steered.csv",
                viz_coords=result.viz_coords,
            )
            # Original space: same cluster colors, original positions
            generate_viz_html(
                result, run_dir / "viz_original.html",
                viz_coords=result.viz_coords_original,
                title=f"{run_name} — Original Embedding Space",
                run_config=run_config,
            )
            _save_viz_coords(
                result, run_dir / "viz_coords_original.csv",
                viz_coords=result.viz_coords_original,
            )
        else:
            generate_viz_html(
                result, run_dir / "viz.html",
                title=run_name,
                run_config=run_config,
            )


def _save_insights(result: PipelineResult, path: Path) -> None:
    """Pretty-printed insights with source texts and full prompt result inline."""
    output = []
    for insight in result.insights:
        entry: dict[str, Any] = {
            "id": insight.id,
            "insight": insight.text,
            "cluster_id": insight.metadata.get("cluster_id"),
        }
        # Include extra fields from the prompt module (confidence, suggestedAction, etc.)
        for key in ("confidence", "suggestedAction"):
            if insight.metadata.get(key) is not None:
                entry[key] = insight.metadata[key]
        # Full raw LLM response for traceability
        if "prompt_result" in insight.metadata:
            entry["prompt_result"] = insight.metadata["prompt_result"]

        entry["source_memories"] = []
        source_ids = insight.metadata.get("source_ids", [])
        source_texts = insight.metadata.get("source_texts", [])
        for sid, stxt in zip(source_ids, source_texts):
            entry["source_memories"].append({"id": sid, "text": stxt})
        output.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _save_clusters(result: PipelineResult, path: Path) -> None:
    """Human-readable cluster breakdown showing all members."""
    output = []
    for cluster_id, chunks in sorted(result.clusters.items()):
        label = "noise" if cluster_id == -1 else f"cluster_{cluster_id}"
        members = []
        for c in chunks:
            member: dict[str, Any] = {"id": c.id, "text": c.text}
            # Include any interesting metadata (skip embedding)
            for k, v in c.metadata.items():
                member[k] = v
            members.append(member)

        cluster_entry: dict[str, Any] = {
            "cluster": label,
            "cluster_id": cluster_id,
            "size": len(chunks),
            "members": members,
        }
        output.append(cluster_entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _save_cluster_texts_md(result: PipelineResult, path: Path) -> None:
    """Human-readable markdown view of clusters with insights and texts."""
    # Group insights by cluster_id
    insights_by_cluster: dict[int, list[MemoryChunk]] = {}
    for insight in result.insights:
        cid = insight.metadata.get("cluster_id")
        if cid is not None:
            insights_by_cluster.setdefault(cid, []).append(insight)

    lines: list[str] = []

    for cluster_id, chunks in sorted(result.clusters.items()):
        label = "Noise" if cluster_id == -1 else f"Cluster {cluster_id}"
        lines.append(f"# {label} ({len(chunks)} texts)")
        lines.append("")

        # Insights section (only if this cluster has insights)
        cluster_insights = insights_by_cluster.get(cluster_id, [])
        if cluster_insights:
            lines.append("## Insights")
            lines.append("")
            for insight in cluster_insights:
                lines.append(f"> **Insight:** {insight.text}")
                if insight.metadata.get("confidence") is not None:
                    lines.append(
                        f"> **Confidence:** {insight.metadata['confidence']}"
                    )
                if insight.metadata.get("suggestedAction"):
                    lines.append(
                        f"> **Suggested Action:** "
                        f"{insight.metadata['suggestedAction']}"
                    )
                lines.append(">")
                lines.append("")

        # Texts section
        lines.append("## Texts")
        lines.append("")

        sorted_chunks = sorted(
            chunks,
            key=lambda c: c.metadata.get("timestamp", ""),
        )
        for i, chunk in enumerate(sorted_chunks, 1):
            lines.append("---")
            lines.append("")
            lines.append(f"**Text {i}**")
            lines.append("")
            lines.append(chunk.text)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _save_run_stats(
    result: PipelineResult,
    path: Path,
    run_config: dict[str, Any],
) -> None:
    """Metadata about the run: config, stats, timing."""
    cluster_sizes = {
        ("noise" if k == -1 else f"cluster_{k}"): len(v)
        for k, v in sorted(result.clusters.items())
    }
    noise_count = len(result.clusters.get(-1, []))
    real_clusters = {k: v for k, v in result.clusters.items() if k != -1}

    stats: dict[str, Any] = {
        "run_name": path.parent.name,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "config": run_config,
        "input": {
            "total_chunks": len(result.input_chunks),
        },
        "clustering": {
            "num_clusters": len(real_clusters),
            "noise_points": noise_count,
            "cluster_sizes": cluster_sizes,
        },
        "synthesis": {
            "total_insights": len(result.insights),
            "insights_per_cluster": {},
        },
    }

    # Count insights per cluster
    for insight in result.insights:
        cid = str(insight.metadata.get("cluster_id", "unknown"))
        key = f"cluster_{cid}"
        stats["synthesis"]["insights_per_cluster"][key] = (
            stats["synthesis"]["insights_per_cluster"].get(key, 0) + 1
        )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _save_viz_coords(
    result: PipelineResult,
    path: Path,
    viz_coords: dict[str, tuple[float, float, float]] | None = None,
) -> None:
    """Save 3D visualization coordinates as CSV: id, cluster_id, x, y, z, text."""
    if viz_coords is None:
        viz_coords = result.viz_coords

    # Build chunk_id -> cluster_id lookup
    id_to_cluster: dict[str, int] = {}
    id_to_text: dict[str, str] = {}
    for cluster_id, chunks in result.clusters.items():
        for chunk in chunks:
            id_to_cluster[chunk.id] = cluster_id
            id_to_text[chunk.id] = chunk.text

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "cluster_id", "x", "y", "z", "text"])
        for chunk_id, (x, y, z) in viz_coords.items():
            writer.writerow([
                chunk_id,
                id_to_cluster.get(chunk_id, -1),
                f"{x:.6f}",
                f"{y:.6f}",
                f"{z:.6f}",
                id_to_text.get(chunk_id, ""),
            ])
