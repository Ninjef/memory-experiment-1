# GEMINI_PARSER — Personal Gemini Chat Log Extractor — 2026-04-05

## What was built

A Python script that parses Google Gemini chat logs exported via Google Takeout (HTML format) into structured JSON, enabling personal conversation data to be used for testing the memory processing pipeline.

---

## Problem

The project needed real conversational data for testing the Zero-Shot Latent Space Steering pipeline. Google Gemini chat logs were available as an HTML export from Google Takeout, but the format is a dense, minified HTML document with Material Design Lite styling — not directly usable by the pipeline. A parser was needed similar to the existing `extract_locomo.py`.

## Solution

Created `rawDataPreFormatted/extract_gemini.py` — a standalone extraction script following the same patterns as `extract_locomo.py`.

### New files

- **`rawDataPreFormatted/extract_gemini.py`** — Main parser script. No external dependencies beyond Python stdlib; uses regex-based parsing since the HTML structure is consistent enough.

### Output structure

- **`rawDataPreFormatted/jeffArnoldGeminiChats_parsedFromHTMLToJson/`** — Output directory, containing timestamped run folders (matching the project's `run_<timestamp>_<adjective>-<noun>` naming convention via `src.naming.generate_run_name`).
- Each run produces:
  - `gemini_chats.json` — Full extraction with metadata and entries array
  - `run_info.json` — Extraction config and parameters

### CLI interface

```
python rawDataPreFormatted/extract_gemini.py <path_to_html> --user "Name" [--output-dir DIR]
```

- Positional arg: path to the HTML file
- `--user` (required): username for metadata
- `--output-dir`: defaults to `rawDataPreFormatted/jeffArnoldGeminiChats_parsedFromHTMLToJson/`

### Parsing strategy

The HTML has a repeating structure of `<div class="outer-cell ...">` blocks, each containing:
1. A header with "Gemini Apps"
2. A content cell with the entry data
3. A footer with "Products:" metadata

Key parsing decisions:
- **Datetime as separator**: A `<br>`-preceded datetime string (e.g., `Apr 3, 2026, 1:36:46 PM MDT`) reliably separates user prompts from AI responses. Only the FIRST datetime match is used per block, preventing false splits on datetime-like strings in response content.
- **Entry type classification**: Detects 7 entry types from content prefixes: `prompted`, `canvas`, `assistant_feature`, `feedback`, `preferred_draft`, `survey`, `used_app`.
- **Dual response format**: AI responses stored as both plain text (`ai_response`) and raw HTML (`ai_response_html`) to support both pipeline consumption and human review.
- **Timezone handling**: Maps common US timezone abbreviations (MDT, MST, EDT, EST, CDT, CST, PDT, PST, PT, MT, CT, ET) to UTC offsets for ISO 8601 output.
- **Unicode normalization**: Handles `\xa0` (NBSP between "Prompted" and prompt text) and `\u202f` (narrow NBSP before AM/PM in timestamps).

### Output JSON format

```json
{
  "date_extracted": "2026-04-05T00:06:32+00:00",
  "user": "Jeff Arnold",
  "source_file": "MyActivity.html",
  "total_entries": 1439,
  "entry_type_counts": {"prompted": 1328, "canvas": 80, ...},
  "entries": [
    {
      "entry_type": "prompted",
      "user_prompt": "plain text prompt",
      "ai_response": "plain text response",
      "ai_response_html": "<p>original HTML</p>",
      "timestamp": "2026-04-03T13:36:46-06:00"
    }
  ]
}
```

### Results from first run

| Entry Type | Count |
|---|---|
| prompted | 1,328 |
| canvas | 80 |
| feedback | 14 |
| assistant_feature | 9 |
| used_app | 5 |
| preferred_draft | 2 |
| survey | 1 |
| **Total** | **1,439** |

- 10 prompted entries have no AI response in the source HTML (multi-turn fragments)
- 78 prompted entries have image-only responses (HTML preserved in `ai_response_html`, plain text is empty since images have no alt text)
- All remaining 1,240 prompted entries have both user prompt and AI response text

### Design decisions

- **No BeautifulSoup**: The HTML structure is regular enough for regex parsing, avoiding a new dependency. The project's `requirements.txt` was left unchanged.
- **`<br>` prefix on datetime regex**: Per user guidance, requiring a `<br>` before the datetime pattern greatly reduces false matches from datetime-like strings appearing inside prompt text.
- **First-match-only splitting**: Only the first datetime match separates prompt from response, preventing incorrect splits when AI responses contain dates.
- **Follows extract_locomo.py conventions**: Uses `generate_run_name()` for output folder naming, writes `run_info.json` metadata, and follows the same CLI/output patterns.

## Task reference

Implements the first script described in `projectTasks/PERSONAL_DATA_PARSING.md`. The second script (further formatting for pipeline consumption) is deferred as specified in that task document.
