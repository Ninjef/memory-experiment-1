import json
import tempfile
from pathlib import Path

import pytest

from src.io import load_chunks, save_chunks, _save_cluster_texts_md, _save_insights
from src.models import MemoryChunk
from src.pipeline import PipelineResult


def test_load_chunks_basic(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text(
        '{"text": "hello", "source": "chat"}\n'
        '{"text": "world", "topic": "work"}\n'
    )
    chunks = load_chunks(f)
    assert len(chunks) == 2
    assert chunks[0].text == "hello"
    assert chunks[0].metadata["source"] == "chat"
    assert chunks[1].text == "world"
    assert chunks[1].metadata["topic"] == "work"


def test_load_chunks_skips_blank_lines(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('{"text": "a"}\n\n{"text": "b"}\n')
    chunks = load_chunks(f)
    assert len(chunks) == 2


def test_load_chunks_missing_text_raises(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('{"source": "chat"}\n')
    with pytest.raises(ValueError, match="missing required 'text' field"):
        load_chunks(f)


def test_save_chunks_strips_embeddings(tmp_path):
    chunks = [
        MemoryChunk(text="test", embedding=[1.0, 2.0, 3.0], metadata={"k": "v"}),
    ]
    out = tmp_path / "out.jsonl"
    save_chunks(chunks, out)

    line = json.loads(out.read_text().strip())
    assert "embedding" not in line
    assert line["text"] == "test"
    assert line["k"] == "v"


def test_round_trip(tmp_path):
    original = [
        MemoryChunk(text="one", metadata={"a": 1}),
        MemoryChunk(text="two", metadata={"b": "hello"}),
    ]
    path = tmp_path / "rt.jsonl"
    save_chunks(original, path)
    loaded = load_chunks(path)

    assert len(loaded) == 2
    assert loaded[0].text == "one"
    assert loaded[0].metadata["a"] == 1
    assert loaded[1].text == "two"
    assert loaded[1].metadata["b"] == "hello"


def _make_result(with_insights=False):
    """Build a minimal PipelineResult for testing output functions."""
    chunks_0 = [
        MemoryChunk(text="Memory about cats", metadata={"timestamp": "2026-01-02"}),
        MemoryChunk(text="Memory about dogs", metadata={"timestamp": "2026-01-01"}),
    ]
    chunks_1 = [
        MemoryChunk(text="Memory about coding", metadata={"timestamp": "2026-01-03"}),
    ]
    noise = [
        MemoryChunk(text="Random noise text", metadata={}),
    ]
    clusters = {0: chunks_0, 1: chunks_1, -1: noise}
    insights = []
    if with_insights:
        insights = [
            MemoryChunk(
                text="Cats and dogs are both pets",
                metadata={
                    "type": "insight",
                    "cluster_id": 0,
                    "source_ids": [c.id for c in chunks_0],
                    "source_texts": [c.text for c in chunks_0],
                    "confidence": 7.5,
                    "suggestedAction": "Consider getting both",
                    "prompt_result": {
                        "insight": "Cats and dogs are both pets",
                        "confidence": 7.5,
                        "suggestedAction": "Consider getting both",
                    },
                },
            ),
        ]
    return PipelineResult(
        insights=insights, clusters=clusters, input_chunks=chunks_0 + chunks_1 + noise
    )


def test_cluster_texts_md_structure(tmp_path):
    result = _make_result(with_insights=False)
    path = tmp_path / "cluster_texts.md"
    _save_cluster_texts_md(result, path)
    content = path.read_text()

    # Should have headers for noise, cluster 0, cluster 1
    assert "# Noise (1 texts)" in content
    assert "# Cluster 0 (2 texts)" in content
    assert "# Cluster 1 (1 texts)" in content

    # Should have text content
    assert "Memory about cats" in content
    assert "Memory about dogs" in content
    assert "Memory about coding" in content

    # Should NOT have Insights section when no insights exist
    assert "## Insights" not in content

    # Should have separator lines
    assert "---" in content


def test_cluster_texts_md_with_insights(tmp_path):
    result = _make_result(with_insights=True)
    path = tmp_path / "cluster_texts.md"
    _save_cluster_texts_md(result, path)
    content = path.read_text()

    # Should have Insights section under cluster 0
    assert "## Insights" in content
    assert "Cats and dogs are both pets" in content
    assert "**Confidence:** 7.5" in content
    assert "**Suggested Action:** Consider getting both" in content


def test_cluster_texts_md_sorts_by_timestamp(tmp_path):
    result = _make_result(with_insights=False)
    path = tmp_path / "cluster_texts.md"
    _save_cluster_texts_md(result, path)
    content = path.read_text()

    # In cluster 0, dogs (2026-01-01) should appear before cats (2026-01-02)
    dogs_pos = content.index("Memory about dogs")
    cats_pos = content.index("Memory about cats")
    assert dogs_pos < cats_pos


def test_insights_json_includes_prompt_result(tmp_path):
    result = _make_result(with_insights=True)
    path = tmp_path / "insights.json"
    _save_insights(result, path)
    data = json.loads(path.read_text())

    assert len(data) == 1
    entry = data[0]
    assert entry["insight"] == "Cats and dogs are both pets"
    assert entry["cluster_id"] == 0
    assert entry["confidence"] == 7.5
    assert entry["suggestedAction"] == "Consider getting both"
    assert "prompt_result" in entry
    assert entry["prompt_result"]["insight"] == "Cats and dogs are both pets"
    assert len(entry["source_memories"]) == 2
