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


def test_pipeline_with_multiple_clusters():
    class MultiClusterer:
        def cluster(self, chunks):
            mid = len(chunks) // 2
            return {0: chunks[:mid], 1: chunks[mid:]}

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
