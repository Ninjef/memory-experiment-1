"""Extract LoCoMo conversation data into pipeline-ready JSONL format.

Usage:
    python rawDataPreFormatted/extract_locomo.py              # one file per conversation pair
    python rawDataPreFormatted/extract_locomo.py --all        # single combined file
    python rawDataPreFormatted/extract_locomo.py --output-dir data/my_output/
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = SCRIPT_DIR / "locomo10.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "locomo"

# Add project root to path so we can import src.naming
sys.path.insert(0, str(PROJECT_ROOT))
from src.naming import generate_run_name


def parse_locomo_datetime(raw: str) -> str:
    """Parse LoCoMo datetime like '1:56 pm on 8 May, 2023' to ISO 8601."""
    try:
        dt = datetime.strptime(raw.strip(), "%I:%M %p on %d %B, %Y")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        print(f"  Warning: could not parse datetime '{raw}', using raw string", file=sys.stderr)
        return raw.strip()


def discover_sessions(conversation: dict) -> list[tuple[int, list, str]]:
    """Find all session_N keys that have message lists and datetimes.

    Returns sorted list of (session_number, messages, datetime_string).
    """
    session_pattern = re.compile(r"^session_(\d+)$")
    sessions = []

    for key, value in conversation.items():
        m = session_pattern.match(key)
        if m and isinstance(value, list):
            n = int(m.group(1))
            dt_key = f"session_{n}_date_time"
            dt_raw = conversation.get(dt_key, "")
            sessions.append((n, value, dt_raw))

    sessions.sort(key=lambda x: x[0])
    return sessions


def extract_entry(entry: dict) -> list[dict]:
    """Extract all messages from one LoCoMo entry into flat dicts."""
    conv = entry["conversation"]
    sample_id = entry.get("sample_id", "unknown")
    speaker_a = conv.get("speaker_a", "unknown")
    speaker_b = conv.get("speaker_b", "unknown")

    records = []
    for session_num, messages, dt_raw in discover_sessions(conv):
        timestamp = parse_locomo_datetime(dt_raw) if dt_raw else ""

        for msg in messages:
            record = {
                "text": msg["text"],
                "timestamp": timestamp,
                "source": "locomo",
                "speaker": msg.get("speaker", "unknown"),
                "dia_id": msg.get("dia_id", ""),
                "session": session_num,
                "sample_id": sample_id,
                "speaker_a": speaker_a,
                "speaker_b": speaker_b,
            }
            # Include optional fields only when present
            for optional in ("img_url", "blip_caption", "query"):
                if optional in msg:
                    record[optional] = msg[optional]

            records.append(record)

    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    """Write records to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_extract_info(run_dir: Path, run_config: dict[str, Any]) -> None:
    """Save extraction metadata to run_info.json, mirroring pipeline output style."""
    info = {
        "run_name": run_dir.name,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "config": run_config,
    }
    with open(run_dir / "run_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Extract LoCoMo data to pipeline JSONL format")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to locomo10.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--all", action="store_true", dest="combine", help="Combine all pairs into one file")
    parser.add_argument("-n", "--limit", type=int, default=None, help="Max records to keep (first N in order)")
    parser.add_argument("--sample", type=int, default=None, help="Randomly sample N records")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for --sample (for reproducibility)")
    args = parser.parse_args()

    if args.limit and args.sample:
        parser.error("--limit and --sample are mutually exclusive")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} conversation entries from {args.input}")

    def apply_filter(records: list[dict]) -> list[dict]:
        if args.sample:
            rng = random.Random(args.seed)
            n = min(args.sample, len(records))
            return rng.sample(records, n)
        if args.limit:
            return records[:args.limit]
        return records

    # Create a run folder with timestamp + fun name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / generate_run_name(args.output_dir, ts)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build config that captures all input parameters
    run_config: dict[str, Any] = {
        "input_file": str(Path(args.input).resolve()),
        "mode": "combined" if args.combine else "per_conversation",
        "limit": args.limit,
        "sample": args.sample,
        "seed": args.seed,
    }

    if args.combine:
        all_records = []
        for entry in data:
            all_records.extend(extract_entry(entry))
        all_records = apply_filter(all_records)
        path = run_dir / f"all_{len(all_records)}records.jsonl"
        write_jsonl(all_records, path)
        run_config["total_records"] = len(all_records)
        run_config["files"] = [path.name]
        print(f"  Wrote {len(all_records)} records -> {path}")
    else:
        total = 0
        filenames = []
        for entry in data:
            records = apply_filter(extract_entry(entry))
            conv = entry["conversation"]
            sample_id = entry.get("sample_id", "unknown")
            sa = conv.get("speaker_a", "unknown").lower().replace(" ", "_")
            sb = conv.get("speaker_b", "unknown").lower().replace(" ", "_")
            filename = f"{sample_id}_{sa}_{sb}_{len(records)}records.jsonl"
            path = run_dir / filename
            write_jsonl(records, path)
            filenames.append(filename)
            print(f"  {conv.get('speaker_a')} & {conv.get('speaker_b')}: {len(records)} records -> {path}")
            total += len(records)
        run_config["total_records"] = total
        run_config["files"] = filenames
        print(f"\nTotal: {total} records across {len(data)} files")

    save_extract_info(run_dir, run_config)
    print(f"\nExtraction saved to {run_dir}/")
    print(f"  run_info.json — extraction config and parameters")


if __name__ == "__main__":
    main()
