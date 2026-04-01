import json
import tempfile
from pathlib import Path

import pytest

from src.io import load_chunks, save_chunks
from src.models import MemoryChunk


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
