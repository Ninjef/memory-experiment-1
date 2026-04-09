"""
Memory Processing Pipeline — CLI Entry Point

Usage:
    python run.py data/sample_input.jsonl
    python run.py data/sample_input.jsonl --output-dir output/my_run
    python run.py data/sample_input.jsonl --model claude-haiku-4-5-20251001
    python run.py data/sample_input.jsonl --steerer projection --themes "financial anxieties" "food and budget" --cluster-only
"""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.clusterers import load_clusterer_module
from src.embedder import DEFAULT_MODEL_NAME, SentenceTransformerEmbedder
from src.io import load_chunks, save_run
from src.naming import generate_run_name
from src.pipeline import Pipeline
from src.prompts import load_prompt
from src.synthesizer import AnthropicSynthesizer, DEFAULT_MODEL


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the memory processing pipeline")
    parser.add_argument("input", help="Path to input JSONL file")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for run output (default: output/run_<timestamp>)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model for synthesis (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--prompt",
        default="default",
        help="Name of prompt module in src/prompts/ (default: 'default'). "
             "Try 'insight_generating' for psychiatry-style insights with confidence scoring.",
    )
    parser.add_argument(
        "--cluster-only",
        action="store_true",
        help="Run only embedding and clustering, skip LLM synthesis (no API key needed)",
    )
    parser.add_argument(
        "--steerer",
        default=None,
        help="Name of steerer module in src/steerers/ (e.g., 'projection'). Omit to skip steering.",
    )
    parser.add_argument(
        "--clusterer",
        default="umap_hdbscan",
        help="Name of clusterer module in src/clusterers/ (default: 'umap_hdbscan'). "
             "Try 'theme_nn' for theme-based nearest-neighbor clustering.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable embedding cache (force fresh computation every run)",
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="Directory for the embedding cache (default: .cache)",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging to see each pipeline step",
    )
    return parser


def main() -> None:
    load_dotenv()

    parser = _build_parser()

    # Two-phase parse: first pass discovers which steerer/clusterer without
    # handling --help, so module-specific args can be registered before help
    # is printed.
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--steerer", default=None)
    pre_parser.add_argument("--clusterer", default="umap_hdbscan")
    pre_args, _ = pre_parser.parse_known_args()

    steerer_module = None
    if pre_args.steerer:
        from src.steerers import load_steerer_module
        steerer_module = load_steerer_module(pre_args.steerer)
        steerer_module.add_args(parser)

    clusterer_module = load_clusterer_module(pre_args.clusterer)
    clusterer_module.add_args(parser)

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Resolve output dir
    if args.output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = Path("output") / generate_run_name(Path("output"), ts)
    else:
        run_dir = Path(args.output_dir)

    # Load input
    chunks = load_chunks(args.input)
    print(f"Loaded {len(chunks)} chunks from {args.input}")

    # Build components
    embedder = SentenceTransformerEmbedder(
        model_name=args.embedding_model or DEFAULT_MODEL_NAME,
        cache_dir=args.cache_dir,
        no_cache=args.no_cache,
    )
    clusterer = clusterer_module.create(args, embedder)
    print(f"Using clusterer: {args.clusterer}")

    steerer = None
    if steerer_module is not None:
        steerer = steerer_module.create(args, embedder)
        print(f"Using steerer: {args.steerer}")

    if args.cluster_only:
        pipeline = Pipeline(
            embedder=embedder,
            clusterer=clusterer,
            synthesizer=None,
            steerer=steerer,
        )
        result = pipeline.run_cluster_only(chunks)
    else:
        prompt_module = load_prompt(args.prompt)
        print(f"Using prompt: {args.prompt}")
        pipeline = Pipeline(
            embedder=embedder,
            clusterer=clusterer,
            synthesizer=AnthropicSynthesizer(
                model=args.model, prompt_module=prompt_module
            ),
            steerer=steerer,
        )
        result = pipeline.run(chunks)

    # Save all output files to the run directory
    run_config = {
        "input_file": str(Path(args.input).resolve()),
        "model": args.model if not args.cluster_only else "n/a (cluster-only)",
        "embedder": embedder.model_name,
        "clusterer": args.clusterer,
        "steerer": args.steerer or "none",
        "prompt": args.prompt if not args.cluster_only else "n/a (cluster-only)",
        "synthesizer": f"Anthropic ({args.model})" if not args.cluster_only else "skipped (cluster-only)",
    }
    if steerer_module is not None:
        run_config["steerer_params"] = {
            k: v for k, v in vars(args).items()
            if k.startswith("steer") or k == "themes" or k == "themes_file"
        }
    if args.clusterer != "umap_hdbscan":
        run_config["clusterer_params"] = {
            k: v for k, v in vars(args).items()
            if k.startswith("cluster_theme") or k.startswith("theme_") or k == "min_cluster_size"
        }
    save_run(result, run_dir, run_config)
    print(f"\nRun saved to {run_dir}/")
    if not args.cluster_only:
        print(f"  insights.json  — {len(result.insights)} insights with source texts")
    print(f"  clusters.json  — {len(result.clusters)} cluster(s) with all members")
    print(f"  cluster_texts.md — cluster texts and insights in readable markdown")
    print(f"  run_info.json  — config and stats")
    if result.viz_coords:
        if result.viz_coords_original:
            print(f"  viz_steered.html / viz_original.html — dual 3D views ({len(result.viz_coords)} points)")
        else:
            print(f"  viz.html       — open in browser for interactive 3D cluster view")

    if not args.cluster_only:
        # Print preview
        print("\n--- Insight Preview ---")
        for i, insight in enumerate(result.insights, 1):
            print(f"\n[{i}] {insight.text}")
            source_count = len(insight.metadata.get("source_ids", []))
            print(f"    (from {source_count} source memories, cluster {insight.metadata.get('cluster_id')})")
    else:
        # Print cluster preview
        print("\n--- Cluster Preview ---")
        for cluster_id, members in sorted(result.clusters.items()):
            label = "Noise" if cluster_id == -1 else f"Cluster {cluster_id}"
            print(f"\n{label} ({len(members)} members):")
            for m in members[:3]:
                print(f"  - {m.text[:80]}{'...' if len(m.text) > 80 else ''}")
            if len(members) > 3:
                print(f"  ... and {len(members) - 3} more")


if __name__ == "__main__":
    main()
