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

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = SCRIPT_DIR / "locomo10.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "locomo"


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


def write_jsonl(records: list[dict], output_dir: Path, filename_stem: str) -> Path:
    """Write records to a JSONL file with count and timestamp in the name."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    count = len(records)
    filename = f"{filename_stem}_{count}records_{ts}.jsonl"
    path = output_dir / filename

    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return path


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

    if args.combine:
        all_records = []
        for entry in data:
            all_records.extend(extract_entry(entry))
        all_records = apply_filter(all_records)
        path = write_jsonl(all_records, args.output_dir, "all")
        print(f"  Wrote {len(all_records)} records -> {path}")
    else:
        total = 0
        for entry in data:
            records = apply_filter(extract_entry(entry))
            conv = entry["conversation"]
            sample_id = entry.get("sample_id", "unknown")
            sa = conv.get("speaker_a", "unknown").lower().replace(" ", "_")
            sb = conv.get("speaker_b", "unknown").lower().replace(" ", "_")
            stem = f"{sample_id}_{sa}_{sb}"
            path = write_jsonl(records, args.output_dir, stem)
            print(f"  {conv.get('speaker_a')} & {conv.get('speaker_b')}: {len(records)} records -> {path}")
            total += len(records)
        print(f"\nTotal: {total} records across {len(data)} files")


if __name__ == "__main__":
    main()
