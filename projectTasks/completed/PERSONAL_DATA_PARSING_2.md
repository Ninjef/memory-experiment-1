# Overview

We did the work outlined in PERSONAL_DATA_PARSING.md, and can now parse out google gemini chat logs. But we haven't yet implemented chunking logic.

# Implementation

For this, we'll switch embedding models to nomic-embed-text-v1.5, and set a chunking window for the texts.