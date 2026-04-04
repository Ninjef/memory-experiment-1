import numpy as np
import pytest

from src.embedding_cache import EmbeddingCache


@pytest.fixture
def cache(tmp_path):
    return EmbeddingCache(cache_dir=tmp_path, model_name="test-model")


def _make_embedding(dim=384):
    return np.random.default_rng(42).random(dim).astype(np.float32).tolist()


def test_put_and_get_roundtrip(cache):
    emb = _make_embedding()
    cache.put_many({"hello world": emb})
    result = cache.get_many(["hello world"])
    assert "hello world" in result
    np.testing.assert_array_almost_equal(result["hello world"], emb, decimal=6)


def test_get_missing_returns_empty(cache):
    result = cache.get_many(["nonexistent text"])
    assert result == {}


def test_put_many_and_get_many(cache):
    entries = {
        "text one": _make_embedding(),
        "text two": _make_embedding(),
        "text three": _make_embedding(),
    }
    cache.put_many(entries)
    result = cache.get_many(list(entries.keys()))
    assert len(result) == 3
    for text, emb in entries.items():
        np.testing.assert_array_almost_equal(result[text], emb, decimal=6)


def test_get_many_partial_hit(cache):
    cache.put_many({"cached": _make_embedding()})
    result = cache.get_many(["cached", "not cached"])
    assert "cached" in result
    assert "not cached" not in result


def test_different_models_separate(tmp_path):
    cache_a = EmbeddingCache(cache_dir=tmp_path, model_name="model-a")
    cache_b = EmbeddingCache(cache_dir=tmp_path, model_name="model-b")
    emb_a = _make_embedding()
    emb_b = [x + 1.0 for x in _make_embedding()]

    cache_a.put_many({"same text": emb_a})
    cache_b.put_many({"same text": emb_b})

    result_a = cache_a.get_many(["same text"])
    result_b = cache_b.get_many(["same text"])
    np.testing.assert_array_almost_equal(result_a["same text"], emb_a, decimal=6)
    np.testing.assert_array_almost_equal(result_b["same text"], emb_b, decimal=6)


def test_cache_persists_across_instances(tmp_path):
    emb = _make_embedding()
    cache1 = EmbeddingCache(cache_dir=tmp_path, model_name="test-model")
    cache1.put_many({"persistent": emb})
    cache1.close()

    cache2 = EmbeddingCache(cache_dir=tmp_path, model_name="test-model")
    result = cache2.get_many(["persistent"])
    assert "persistent" in result
    np.testing.assert_array_almost_equal(result["persistent"], emb, decimal=6)
    cache2.close()


def test_clear_removes_all(cache):
    cache.put_many({"a": _make_embedding(), "b": _make_embedding()})
    cache.clear()
    result = cache.get_many(["a", "b"])
    assert result == {}


def test_get_many_empty_list(cache):
    assert cache.get_many([]) == {}


def test_put_many_empty_dict(cache):
    cache.put_many({})  # Should not raise
