#!/usr/bin/env python3
"""Convert extracted Gemini chat JSON into chunked JSONL for the pipeline.

Reads gemini_chats.json (output of extract_gemini.py) and produces a JSONL file
where each line is a MemoryChunk-compatible dict with a "text" field and metadata.

Long conversations are split on paragraph boundaries with overlap.

Usage:
    python scripts/chunk_gemini_chats.py \
        rawDataPreFormatted/jeffArnoldGeminiChats_parsedFromHTMLToJson/run_*/gemini_chats.json \
        --output data/gemini_chats.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


DEFAULT_MAX_CHUNK_CHARS = 5000
DEFAULT_ENTRY_TYPES = ["prompted", "canvas"]


def _deterministic_id(entry_index: int, chunk_index: int) -> str:
    """Generate a reproducible UUID-like ID from entry and chunk indices."""
    raw = f"gemini:{entry_index}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split text on paragraph boundaries, greedily accumulating up to max_chars.

    Returns a list of chunks. Adjacent chunks overlap by one paragraph.
    """
    paragraphs = text.split("\n\n")
    # Filter out empty paragraphs but preserve whitespace-only ones
    paragraphs = [p for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for i, para in enumerate(paragraphs):
        para_len = len(para) + (2 if current_parts else 0)  # account for \n\n joiner

        if current_parts and current_len + para_len > max_chars:
            # Flush current chunk
            chunks.append("\n\n".join(current_parts))
            # Overlap: start next chunk with the last paragraph of the previous
            last = current_parts[-1]
            current_parts = [last]
            current_len = len(last)

        current_parts.append(para)
        current_len += para_len

    # Flush remaining
    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks


def _chunk_entry(
    entry: dict,
    entry_index: int,
    max_chars: int,
    user_prompts_only: bool = False,
) -> list[dict]:
    """Convert a single Gemini entry into one or more JSONL-ready dicts."""
    entry_type = entry["entry_type"]
    timestamp = entry.get("timestamp", "")
    user_prompt = (entry.get("user_prompt") or "").strip()
    ai_response = (entry.get("ai_response") or "").strip()
    canvas_title = (entry.get("canvas_title") or "").strip()

    # Skip entries with no text content
    if not user_prompt and not ai_response and not canvas_title:
        return []

    # User-prompts-only mode: emit just the user's question as the chunk
    if user_prompts_only:
        if not user_prompt:
            return []
        return [{
            "id": _deterministic_id(entry_index, 0),
            "text": user_prompt,
            "timestamp": timestamp,
            "source": "gemini",
            "entry_type": entry_type,
            "entry_index": entry_index,
            "chunk_index": 0,
            "total_chunks": 1,
        }]

    # Build the context label (short or truncated for inline use)
    if entry_type == "canvas" and canvas_title:
        context_label = f"Canvas: {canvas_title}"
    elif user_prompt:
        context_label = f"User: {user_prompt}"
    else:
        context_label = ""

    # If the context label itself is too long, truncate what goes inline
    # and keep the full version in metadata only
    MAX_INLINE_PREFIX = max_chars // 3
    if len(context_label) > MAX_INLINE_PREFIX:
        inline_prefix = context_label[:MAX_INLINE_PREFIX] + "..."
    else:
        inline_prefix = context_label

    # Build the combined text
    if inline_prefix and ai_response:
        combined = f"{inline_prefix}\n\nAssistant: {ai_response}"
    elif inline_prefix:
        combined = inline_prefix
    elif ai_response:
        combined = ai_response
    else:
        return []

    base_metadata = {
        "timestamp": timestamp,
        "source": "gemini",
        "entry_type": entry_type,
        "entry_index": entry_index,
    }
    if user_prompt:
        base_metadata["user_prompt"] = user_prompt
    if canvas_title:
        base_metadata["canvas_title"] = canvas_title

    # Short enough for a single chunk
    if len(combined) <= max_chars:
        return [{
            "id": _deterministic_id(entry_index, 0),
            "text": combined,
            **base_metadata,
            "chunk_index": 0,
            "total_chunks": 1,
        }]

    # Need to split: chunk the ai_response, first chunk gets prefix inline
    prefix_budget = len(inline_prefix) + 20  # room for "\n\nAssistant: "
    response_chunks = _split_paragraphs(ai_response, max_chars - prefix_budget)

    if not response_chunks:
        # Response was empty but combined was over limit due to prefix alone
        # Just emit the combined text as-is (the prefix carries the meaning)
        return [{
            "id": _deterministic_id(entry_index, 0),
            "text": combined,
            **base_metadata,
            "chunk_index": 0,
            "total_chunks": 1,
        }]

    results = []
    total = len(response_chunks)
    for i, chunk_text in enumerate(response_chunks):
        if i == 0 and inline_prefix:
            text = f"{inline_prefix}\n\nAssistant: {chunk_text}"
        else:
            text = chunk_text

        results.append({
            "id": _deterministic_id(entry_index, i),
            "text": text,
            **base_metadata,
            "chunk_index": i,
            "total_chunks": total,
        })

    return results


def chunk_gemini_json(
    input_path: Path,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    entry_types: list[str] | None = None,
    user_prompts_only: bool = False,
) -> list[dict]:
    """Load a gemini_chats.json file and return chunked dicts."""
    allowed_types = set(entry_types or DEFAULT_ENTRY_TYPES)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_chunks = []
    skipped = {"no_text": 0, "filtered_type": 0}

    for entry_index, entry in enumerate(data["entries"]):
        if entry["entry_type"] not in allowed_types:
            skipped["filtered_type"] += 1
            continue

        chunks = _chunk_entry(entry, entry_index, max_chars, user_prompts_only)
        if not chunks:
            skipped["no_text"] += 1
            continue

        all_chunks.extend(chunks)

    return all_chunks, skipped, data["total_entries"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chunk Gemini chat JSON into pipeline-ready JSONL"
    )
    parser.add_argument("input", help="Path to gemini_chats.json")
    parser.add_argument(
        "--output",
        default="data/gemini_chats.jsonl",
        help="Output JSONL path (default: data/gemini_chats.jsonl)",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=DEFAULT_MAX_CHUNK_CHARS,
        help=f"Max characters per chunk (default: {DEFAULT_MAX_CHUNK_CHARS})",
    )
    parser.add_argument(
        "--entry-types",
        nargs="+",
        default=DEFAULT_ENTRY_TYPES,
        help=f"Entry types to include (default: {' '.join(DEFAULT_ENTRY_TYPES)})",
    )
    parser.add_argument(
        "--user-prompts-only",
        action="store_true",
        help="Only export user prompts (no AI responses)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    chunks, skipped, total_entries = chunk_gemini_json(
        input_path, args.max_chunk_chars, args.entry_types, args.user_prompts_only
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Summary
    entries_used = total_entries - skipped["filtered_type"] - skipped["no_text"]
    multi_chunk = sum(1 for c in chunks if c["chunk_index"] > 0)
    print(f"Input:  {total_entries} entries from {input_path.name}")
    print(f"Filter: {skipped['filtered_type']} skipped (type), {skipped['no_text']} skipped (no text)")
    print(f"Output: {len(chunks)} chunks from {entries_used} entries -> {output_path}")
    if multi_chunk:
        split_entries = len({c["entry_index"] for c in chunks if c["total_chunks"] > 1})
        print(f"  {split_entries} entries were split into multiple chunks")

    # Length stats
    lengths = [len(c["text"]) for c in chunks]
    if lengths:
        print(f"  Chunk lengths: min={min(lengths)}, median={sorted(lengths)[len(lengths)//2]}, max={max(lengths)}")


if __name__ == "__main__":
    main()
