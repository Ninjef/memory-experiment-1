import numpy as np

from src.models import MemoryChunk
from src.pipeline import Pipeline


class MockEmbedder:
    def embed(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        for i, c in enumerate(chunks):
            c.embedding = [float(i)] * 3
        return chunks


class MockClusterer:
    def cluster(self, chunks: list[MemoryChunk]) -> dict[int, list[MemoryChunk]]:
        # Put all chunks in one cluster
        return {0: chunks}

    def reduce_for_viz(self, chunks, n_components=3):
        return np.zeros((len(chunks), n_components))


class MockSynthesizer:
    def synthesize(self, clusters: dict[int, list[MemoryChunk]]) -> list[MemoryChunk]:
        insights = []
        for cluster_id, chunks in clusters.items():
            insights.append(
                MemoryChunk(
                    text=f"Insight from cluster {cluster_id} ({len(chunks)} memories)",
                    metadata={
                        "type": "insight",
                        "source_ids": [c.id for c in chunks],
                        "cluster_id": cluster_id,
                    },
                )
            )
        return insights


def test_pipeline_runs_all_stages():
    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MockClusterer(),
        synthesizer=MockSynthesizer(),
    )
    chunks = [
        MemoryChunk(text="memory one"),
        MemoryChunk(text="memory two"),
        MemoryChunk(text="memory three"),
    ]
    result = pipeline.run(chunks)

    assert len(result.insights) == 1
    assert "Insight from cluster 0" in result.insights[0].text
    assert result.insights[0].metadata["type"] == "insight"
    assert len(result.insights[0].metadata["source_ids"]) == 3
    assert result.clusters == {0: chunks}
    assert result.input_chunks is chunks


def test_pipeline_preserves_embeddings_after_embed():
    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MockClusterer(),
        synthesizer=MockSynthesizer(),
    )
    chunks = [MemoryChunk(text="test")]
    pipeline.run(chunks)
    assert chunks[0].embedding is not None


class MockSteerer:
    def __init__(self):
        self.called = False

    def steer(self, chunks: list[MemoryChunk]) -> list[MemoryChunk]:
        self.called = True
        # Double the first element of each embedding to prove steering ran
        for c in chunks:
            c.embedding[0] *= 2.0
        return chunks


def test_pipeline_with_steerer():
    steerer = MockSteerer()
    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MockClusterer(),
        synthesizer=MockSynthesizer(),
        steerer=steerer,
    )
    chunks = [MemoryChunk(text="test steering")]
    result = pipeline.run(chunks)

    assert steerer.called
    assert chunks[0].embedding[0] == 0.0  # 0.0 * 2 = 0.0 (first chunk gets [0,0,0])
    assert len(result.insights) == 1


def test_pipeline_without_steerer_backward_compat():
    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MockClusterer(),
        synthesizer=MockSynthesizer(),
    )
    chunks = [MemoryChunk(text="no steerer")]
    result = pipeline.run(chunks)

    assert len(result.insights) == 1
    assert chunks[0].embedding == [0.0, 0.0, 0.0]


def test_pipeline_cluster_only_with_steerer():
    steerer = MockSteerer()
    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MockClusterer(),
        synthesizer=None,
        steerer=steerer,
    )
    chunks = [MemoryChunk(text="cluster only steered")]
    result = pipeline.run_cluster_only(chunks)

    assert steerer.called
    assert result.insights == []
    assert len(result.clusters) == 1


def test_pipeline_with_multiple_clusters():
    class MultiClusterer:
        def cluster(self, chunks):
            mid = len(chunks) // 2
            return {0: chunks[:mid], 1: chunks[mid:]}

        def reduce_for_viz(self, chunks, n_components=3):
            return np.zeros((len(chunks), n_components))

    pipeline = Pipeline(
        embedder=MockEmbedder(),
        clusterer=MultiClusterer(),
        synthesizer=MockSynthesizer(),
    )
    chunks = [MemoryChunk(text=f"m{i}") for i in range(6)]
    result = pipeline.run(chunks)

    assert len(result.insights) == 2
    assert result.insights[0].metadata["cluster_id"] == 0
    assert result.insights[1].metadata["cluster_id"] == 1
