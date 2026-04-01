# SECOND_STEP Implementation — 2026-04-01

## What was built
Two additions per SECOND_STEP.md: a dataset extraction script for LoCoMo data, and a `--cluster-only` mode for the pipeline.

## 1. LoCoMo Extraction Script

`rawDataPreFormatted/extract_locomo.py` — converts the LoCoMo conversation dataset (`rawDataPreFormatted/locomo10.json`) into pipeline-ready JSONL.

### Source data
LoCoMo dataset: 10 conversation pairs, ~5,882 total dialogue turns across multiple sessions. Each entry has two speakers, multiple numbered sessions with timestamps, and per-message fields (speaker, dia_id, text, optional image data).

### What it does
- Discovers sessions dynamically (handles gaps in session numbering)
- Parses LoCoMo datetimes (`"1:56 pm on 8 May, 2023"` → ISO 8601) with fallback on parse failure
- Outputs flat JSONL with `text` + metadata: `timestamp`, `source`, `speaker`, `dia_id`, `session`, `sample_id`, `speaker_a`, `speaker_b`, and optional `img_url`/`blip_caption`/`query`
- Output goes to `data/locomo/` with filenames including sample_id, speakers, record count, and timestamp

### CLI flags
| Flag | Purpose |
|---|---|
| `--all` | Combine all 10 pairs into one file (default: one file per pair) |
| `-n / --limit N` | Keep first N records (in order) |
| `--sample N` | Randomly sample N records |
| `--seed S` | Reproducible random sampling |
| `--output-dir` | Override output location |

### Usage
```bash
python rawDataPreFormatted/extract_locomo.py                    # 10 per-pair files
python rawDataPreFormatted/extract_locomo.py --all              # 1 combined file
python rawDataPreFormatted/extract_locomo.py --all -n 100       # first 100 records
python rawDataPreFormatted/extract_locomo.py --all --sample 50  # random 50
```

## 2. Cluster-Only Pipeline Mode

Added `--cluster-only` flag to `run.py` and `run_cluster_only()` method to `Pipeline`.

### Purpose
Allows inspecting clustering results without paying for Anthropic API calls. No API key needed.

### What changed
- `src/pipeline.py` — added `run_cluster_only()`: runs embed → cluster, returns `PipelineResult` with empty insights
- `run.py` — added `--cluster-only` flag; skips synthesizer creation, adjusts output summary, prints cluster preview with first 3 member texts per cluster

### Usage
```bash
python run.py data/sample_input.jsonl --cluster-only
python run.py data/locomo/conv-26_caroline_melanie_419records_*.jsonl --cluster-only
```

## Files created/modified
```
rawDataPreFormatted/extract_locomo.py  — NEW: LoCoMo extraction script
src/pipeline.py                        — MODIFIED: added run_cluster_only()
run.py                                 — MODIFIED: added --cluster-only flag
```

## Key decisions
| Decision | Choice | Rationale |
|---|---|---|
| Script location | `rawDataPreFormatted/extract_locomo.py` | Lives next to its data; each dataset gets its own script since formats vary |
| Per-pair default | One JSONL per conversation pair | ~500-600 msgs per pair is a better fit for UMAP+HDBSCAN than all 5,882 at once |
| Filtering | -n (ordered) and --sample (random) | Enables cheap iteration on subsets without processing full dataset |
| Cluster-only | Separate Pipeline method | Clean separation; no synthesizer instantiation needed |
