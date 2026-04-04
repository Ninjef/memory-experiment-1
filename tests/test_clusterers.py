import numpy as np
import pytest

from src.clusterers import load_clusterer_module
from src.clusterers.hdbscan_direct import HDBSCANDirectClusterer
from src.clusterers.hdbscan_umap import HDBSCANUMAPClusterer
from src.models import MemoryChunk


def _make_chunks(n: int, dim: int = 10) -> list[MemoryChunk]:
    """Create chunks with random embeddings."""
    rng = np.random.default_rng(42)
    return [
        MemoryChunk(text=f"chunk {i}", embedding=rng.random(dim).tolist())
        for i in range(n)
    ]


def _make_clustered_chunks(dim: int = 10) -> list[MemoryChunk]:
    """Create chunks with two tight clusters for reliable HDBSCAN results."""
    rng = np.random.default_rng(42)
    chunks = []
    # Cluster A: centered at 0
    for i in range(10):
        emb = (rng.random(dim) * 0.1).tolist()
        chunks.append(MemoryChunk(text=f"cluster_a_{i}", embedding=emb))
    # Cluster B: centered at 5
    for i in range(10):
        emb = (5.0 + rng.random(dim) * 0.1).tolist()
        chunks.append(MemoryChunk(text=f"cluster_b_{i}", embedding=emb))
    return chunks


# --- HDBSCANDirectClusterer tests ---


class TestHDBSCANDirect:
    def test_returns_clusters(self):
        chunks = _make_clustered_chunks()
        clusterer = HDBSCANDirectClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        assert isinstance(result, dict)
        assert len(result) >= 1
        # All chunks accounted for
        total = sum(len(v) for v in result.values())
        assert total == len(chunks)

    def test_too_few_chunks_returns_single_cluster(self):
        chunks = _make_chunks(2)
        clusterer = HDBSCANDirectClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        assert result == {0: chunks}

    def test_preserves_chunk_objects(self):
        chunks = _make_clustered_chunks()
        clusterer = HDBSCANDirectClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        all_result_chunks = [c for members in result.values() for c in members]
        assert set(id(c) for c in all_result_chunks) == set(id(c) for c in chunks)

    def test_reduce_for_viz(self):
        chunks = _make_chunks(10, dim=20)
        clusterer = HDBSCANDirectClusterer()
        coords = clusterer.reduce_for_viz(chunks, n_components=3)
        assert coords.shape == (10, 3)

    def test_embeddings_unchanged(self):
        """HDBSCAN direct should not modify chunk embeddings."""
        chunks = _make_clustered_chunks()
        original_embeddings = [c.embedding[:] for c in chunks]
        clusterer = HDBSCANDirectClusterer(min_cluster_size=3)
        clusterer.cluster(chunks)
        for chunk, orig in zip(chunks, original_embeddings):
            assert chunk.embedding == orig


# --- HDBSCANUMAPClusterer tests ---


class TestHDBSCANUMAP:
    def test_returns_clusters(self):
        chunks = _make_clustered_chunks()
        clusterer = HDBSCANUMAPClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        assert isinstance(result, dict)
        assert len(result) >= 1
        total = sum(len(v) for v in result.values())
        assert total == len(chunks)

    def test_too_few_chunks_returns_single_cluster(self):
        chunks = _make_chunks(2)
        clusterer = HDBSCANUMAPClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        assert result == {0: chunks}

    def test_embeddings_reduced_after_cluster(self):
        """After clustering, embeddings should be UMAP-reduced (lower dim)."""
        chunks = _make_clustered_chunks(dim=50)
        clusterer = HDBSCANUMAPClusterer(
            min_cluster_size=3, umap_n_components=10
        )
        clusterer.cluster(chunks)
        # Embeddings should now be 10-dim (or fewer if n_chunks-1 < 10)
        for chunk in chunks:
            assert len(chunk.embedding) <= 10

    def test_preserves_chunk_objects(self):
        chunks = _make_clustered_chunks()
        clusterer = HDBSCANUMAPClusterer(min_cluster_size=3)
        result = clusterer.cluster(chunks)
        all_result_chunks = [c for members in result.values() for c in members]
        assert set(id(c) for c in all_result_chunks) == set(id(c) for c in chunks)

    def test_reduce_for_viz(self):
        chunks = _make_chunks(10, dim=20)
        clusterer = HDBSCANUMAPClusterer()
        coords = clusterer.reduce_for_viz(chunks, n_components=3)
        assert coords.shape == (10, 3)


# --- Module loading tests ---


class TestModuleLoading:
    def test_load_hdbscan_direct(self):
        module = load_clusterer_module("hdbscan_direct")
        assert hasattr(module, "add_args")
        assert hasattr(module, "create")
        assert hasattr(module, "HDBSCANDirectClusterer")

    def test_load_hdbscan_umap(self):
        module = load_clusterer_module("hdbscan_umap")
        assert hasattr(module, "add_args")
        assert hasattr(module, "create")
        assert hasattr(module, "HDBSCANUMAPClusterer")
