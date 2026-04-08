"""Extract Google Gemini chat logs from HTML export into structured JSON.

Usage:
    python rawDataPreFormatted/extract_gemini.py rawDataPreFormatted/jeffArnoldGeminiChats/MyActivity.html --user "Jeff Arnold"
    python rawDataPreFormatted/extract_gemini.py path/to/MyActivity.html --user "Name" --output-dir my_output/
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to path so we can import src.naming
sys.path.insert(0, str(PROJECT_ROOT))
from src.naming import generate_run_name

DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "jeffArnoldGeminiChats_parsedFromHTMLToJson"

# Timezone abbreviation -> UTC offset string
TZ_OFFSETS = {
    "MDT": "-06:00", "MST": "-07:00",
    "EDT": "-04:00", "EST": "-05:00",
    "CDT": "-05:00", "CST": "-06:00",
    "PDT": "-07:00", "PST": "-08:00",
    "PT": "-07:00", "MT": "-06:00", "CT": "-05:00", "ET": "-04:00",
    "UTC": "+00:00", "GMT": "+00:00",
}

# Datetime pattern: "Apr 3, 2026, 1:36:46 PM MDT"
# Requires <br> before it to avoid matching datetimes inside prompt text.
# \xa0 and \u202f are treated as whitespace via prior normalization.
DATETIME_RE = re.compile(
    r'<br>\s*'
    r'([A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2}:\d{2} [AP]M ([A-Z]{2,4}))'
    r'\s*<br>'
)


def parse_gemini_datetime(raw: str, tz_abbr: str) -> str:
    """Parse a Gemini datetime string to ISO 8601 with timezone offset."""
    try:
        # Strip the timezone abbreviation suffix before parsing
        dt_str = raw.rsplit(" ", 1)[0]  # "Apr 3, 2026, 1:36:46 PM"
        dt = datetime.strptime(dt_str, "%b %d, %Y, %I:%M:%S %p")
        offset = TZ_OFFSETS.get(tz_abbr, "")
        if offset:
            return dt.strftime("%Y-%m-%dT%H:%M:%S") + offset
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        print(f"  Warning: could not parse datetime '{raw}', using raw", file=sys.stderr)
        return raw


def strip_html(text: str, normalize_whitespace: bool = True) -> str:
    """Remove HTML tags and decode entities to plain text."""
    # Replace <br> and block-level tags with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</(p|div|h[1-6]|li|tr|table|blockquote|hr)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(p|div|h[1-6]|hr|table|blockquote)[\s>]', '\n', text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)

    if normalize_whitespace:
        # Strip trailing whitespace from each line
        lines = [line.rstrip() for line in text.splitlines()]
        # Remove leading indentation that's purely from HTML nesting
        lines = [line.lstrip() for line in lines]
        text = '\n'.join(lines)
        # Collapse runs of blank lines down to at most one
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove leading/trailing blank lines
        text = text.strip()
    else:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

    return text


def classify_entry(content_text: str) -> tuple[str, str]:
    """Classify entry type from the beginning of content cell text.

    Returns (entry_type, remaining_text_after_prefix).
    """
    # Normalize NBSP (\xa0) to regular space for matching
    normalized = content_text.replace('\xa0', ' ')

    if normalized.startswith('Prompted '):
        return 'prompted', content_text[content_text.index('\xa0') + 1:] if '\xa0' in content_text else content_text[len('Prompted '):]
    if normalized.startswith('Created Gemini Canvas titled '):
        prefix = 'Created Gemini Canvas titled '
        return 'canvas', normalized[len(prefix):]
    if normalized.startswith('Used an Assistant feature'):
        return 'assistant_feature', ''
    if normalized.startswith('Gave feedback:'):
        return 'feedback', normalized[len('Gave feedback:'):].strip()
    if normalized.startswith('Selected preferred draft'):
        return 'preferred_draft', ''
    if normalized.startswith('Answered survey question'):
        return 'survey', ''
    if normalized.startswith('Used Gemini Apps'):
        return 'used_app', ''
    return 'unknown', normalized


def extract_blocks(full_html: str) -> list[str]:
    """Split the HTML into individual entry blocks based on outer-cell divs."""
    starts = [m.start() for m in re.finditer(r'<div class="outer-cell', full_html)]
    blocks = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(full_html)
        blocks.append(full_html[s:end])
    return blocks


def parse_block(block_html: str, normalize_whitespace: bool = True) -> dict | None:
    """Parse a single outer-cell block into a structured entry dict."""
    # Find the content cell (6-col, body-1, NOT text-right)
    content_match = re.search(
        r'<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">(.*?)</div>'
        r'<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1 mdl-typography--text-right">',
        block_html, re.DOTALL
    )
    if not content_match:
        return None

    content = content_match.group(1)

    # Normalize unicode whitespace for datetime matching
    content_normalized = content.replace('\u202f', ' ').replace('\xa0', ' ')

    # Classify entry type
    entry_type, remaining = classify_entry(content.strip())

    # Find the FIRST datetime match (must be preceded by <br>)
    dt_match = DATETIME_RE.search(content_normalized)

    timestamp = ""
    if dt_match:
        raw_dt = dt_match.group(1)
        tz_abbr = dt_match.group(2)
        timestamp = parse_gemini_datetime(raw_dt, tz_abbr)

    result = {
        "entry_type": entry_type,
        "timestamp": timestamp,
    }

    if entry_type == 'prompted' and dt_match:
        # Everything before the datetime <br> is the user prompt
        # We need to work with the original content to preserve text
        content_for_split = content.replace('\u202f', ' ')
        prompt_end = dt_match.start()
        prompt_html = content_for_split[:prompt_end]
        # Remove the leading "Prompted\xa0" or "Prompted "
        prompt_html = re.sub(r'^Prompted[\s\xa0]', '', prompt_html.strip())
        # Remove trailing <br>
        prompt_html = re.sub(r'<br>\s*$', '', prompt_html)

        # Everything after the datetime <br> is the AI response
        response_start = dt_match.end()
        response_html = content_for_split[response_start:]
        # Trim trailing <br> before the div closes
        response_html = re.sub(r'<br>\s*$', '', response_html.strip())

        result["user_prompt"] = strip_html(prompt_html, normalize_whitespace)
        result["ai_response"] = strip_html(response_html, normalize_whitespace)
        result["ai_response_html"] = response_html.strip()

    elif entry_type == 'canvas' and dt_match:
        # Canvas: "Created Gemini Canvas titled TITLE<br>CONTENT...<br>DATETIME<br>"
        # The datetime is at the END (after content), so everything before it is content
        content_for_split = content.replace('\u202f', ' ')
        before_dt = content_for_split[:dt_match.start()]
        # Remove the prefix
        before_dt = re.sub(r'^Created Gemini Canvas titled\s*', '', before_dt.strip(), flags=re.IGNORECASE)
        # Split title from body: title is before the first <br>
        title_match = re.match(r'(.*?)<br>(.*)', before_dt, re.DOTALL)
        if title_match:
            result["canvas_title"] = strip_html(title_match.group(1), normalize_whitespace)
            result["ai_response"] = strip_html(title_match.group(2), normalize_whitespace)
            result["ai_response_html"] = title_match.group(2).strip()
        else:
            result["canvas_title"] = strip_html(before_dt, normalize_whitespace)
            result["ai_response"] = ""
            result["ai_response_html"] = ""

    elif entry_type == 'feedback':
        result["feedback_detail"] = remaining

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract Gemini chat logs from HTML to JSON")
    parser.add_argument("input", type=Path, help="Path to MyActivity.html")
    parser.add_argument("--user", required=True, help="Username for metadata")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--raw-whitespace", action="store_true",
                        help="Preserve original whitespace/indentation from HTML (default: normalize)")
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")

    print(f"Reading {args.input}...")
    raw_html = args.input.read_text(encoding="utf-8")

    blocks = extract_blocks(raw_html)
    print(f"Found {len(blocks)} entry blocks")

    entries = []
    type_counts: Counter = Counter()
    skipped = 0

    for block in blocks:
        entry = parse_block(block, normalize_whitespace=not args.raw_whitespace)
        if entry is None:
            skipped += 1
            continue
        type_counts[entry["entry_type"]] += 1
        entries.append(entry)

    # Build output structure
    output = {
        "date_extracted": datetime.now(timezone.utc).isoformat(),
        "user": args.user,
        "source_file": args.input.name,
        "total_entries": len(entries),
        "entry_type_counts": dict(type_counts.most_common()),
        "entries": entries,
    }

    if skipped:
        print(f"  Skipped {skipped} blocks (could not parse)")

    # Create output directory with run name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = args.output_dir / generate_run_name(args.output_dir, ts)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write main output
    out_path = run_dir / "gemini_chats.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Write run info
    run_info = {
        "run_name": run_dir.name,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "input_file": str(args.input.resolve()),
            "user": args.user,
            "total_entries": len(entries),
            "entry_type_counts": dict(type_counts.most_common()),
        },
    }
    with open(run_dir / "run_info.json", "w", encoding="utf-8") as f:
        json.dump(run_info, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Print summary
    print(f"\nExtracted {len(entries)} entries:")
    for etype, count in type_counts.most_common():
        print(f"  {etype}: {count}")
    print(f"\nOutput saved to {run_dir}/")
    print(f"  gemini_chats.json — {len(entries)} entries")
    print(f"  run_info.json — extraction metadata")


if __name__ == "__main__":
    main()
