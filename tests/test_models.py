from src.models import MemoryChunk


def test_memory_chunk_creation():
    chunk = MemoryChunk(text="hello world")
    assert chunk.text == "hello world"
    assert chunk.metadata == {}
    assert chunk.embedding is None
    assert chunk.id  # has a uuid


def test_memory_chunk_with_metadata():
    chunk = MemoryChunk(
        text="test",
        metadata={"timestamp": "2025-01-01", "source": "chat"},
    )
    assert chunk.metadata["timestamp"] == "2025-01-01"
    assert chunk.metadata["source"] == "chat"


def test_to_dict_excludes_embedding_by_default():
    chunk = MemoryChunk(text="test", embedding=[1.0, 2.0, 3.0])
    d = chunk.to_dict()
    assert "embedding" not in d
    assert d["text"] == "test"


def test_to_dict_includes_embedding_when_requested():
    chunk = MemoryChunk(text="test", embedding=[1.0, 2.0])
    d = chunk.to_dict(include_embedding=True)
    assert d["embedding"] == [1.0, 2.0]


def test_to_dict_flattens_metadata():
    chunk = MemoryChunk(text="test", metadata={"source": "chat", "topic": "health"})
    d = chunk.to_dict()
    assert d["source"] == "chat"
    assert d["topic"] == "health"


def test_from_dict_round_trip():
    original = {"text": "hello", "id": "abc123", "source": "journal", "topic": "work"}
    chunk = MemoryChunk.from_dict(dict(original))  # copy since from_dict pops
    assert chunk.text == "hello"
    assert chunk.id == "abc123"
    assert chunk.metadata == {"source": "journal", "topic": "work"}


def test_from_dict_generates_id_if_missing():
    chunk = MemoryChunk.from_dict({"text": "no id here"})
    assert chunk.id  # generated uuid
    assert chunk.text == "no id here"
