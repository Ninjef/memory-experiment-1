import numpy as np
import pytest

from src.models import MemoryChunk
from src.steerers import load_steerer_module
from src.steerers.projection import ProjectionSteerer


def _make_chunks(embeddings: list[list[float]]) -> list[MemoryChunk]:
    return [
        MemoryChunk(text=f"chunk {i}", embedding=emb)
        for i, emb in enumerate(embeddings)
    ]


class TestProjectionSteerer:
    def test_alpha_one_is_identity(self):
        """alpha=1.0 means no amplification — output should equal input."""
        theme = np.array([[1.0, 0.0, 0.0]])
        steerer = ProjectionSteerer(theme_embeddings=theme, alpha=1.0)

        original = [[0.3, 0.7, 0.5], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        chunks = _make_chunks(original)
        result = steerer.steer(chunks)

        for chunk, orig in zip(result, original):
            np.testing.assert_allclose(chunk.embedding, orig, atol=1e-12)

    def test_alpha_two_doubles_theme_component(self):
        """alpha=2.0 should double the projection onto the theme."""
        theme = np.array([[1.0, 0.0, 0.0]])  # x-axis theme
        steerer = ProjectionSteerer(theme_embeddings=theme, alpha=2.0)

        chunks = _make_chunks([[3.0, 4.0, 5.0]])
        steerer.steer(chunks)

        # Original: [3, 4, 5]. Projection onto x-axis: [3, 0, 0].
        # steered = [3,4,5] + (2-1)*[3,0,0] = [6, 4, 5]
        np.testing.assert_allclose(chunks[0].embedding, [6.0, 4.0, 5.0], atol=1e-12)

    def test_orthogonal_embedding_unaffected(self):
        """An embedding orthogonal to the theme should not change."""
        theme = np.array([[1.0, 0.0, 0.0]])  # x-axis
        steerer = ProjectionSteerer(theme_embeddings=theme, alpha=5.0)

        chunks = _make_chunks([[0.0, 3.0, 4.0]])  # no x-component
        steerer.steer(chunks)

        np.testing.assert_allclose(chunks[0].embedding, [0.0, 3.0, 4.0], atol=1e-12)

    def test_multiple_themes(self):
        """Multiple themes should each amplify their own direction."""
        themes = np.array([
            [1.0, 0.0, 0.0],  # x-axis
            [0.0, 1.0, 0.0],  # y-axis
        ])
        steerer = ProjectionSteerer(theme_embeddings=themes, alpha=2.0)

        chunks = _make_chunks([[2.0, 3.0, 5.0]])
        steerer.steer(chunks)

        # After x-theme: [2,3,5] + 1*[2,0,0] = [4, 3, 5]
        # After y-theme: [4,3,5] + 1*[0,3,0] = [4, 6, 5]
        np.testing.assert_allclose(chunks[0].embedding, [4.0, 6.0, 5.0], atol=1e-12)

    def test_preserves_chunk_count(self):
        theme = np.array([[1.0, 0.0, 0.0]])
        steerer = ProjectionSteerer(theme_embeddings=theme, alpha=2.0)

        chunks = _make_chunks([[1.0, 0.0, 0.0]] * 5)
        result = steerer.steer(chunks)
        assert len(result) == 5

    def test_zero_theme_vector_skipped(self):
        """A zero theme vector should not cause errors."""
        themes = np.array([[0.0, 0.0, 0.0]])
        steerer = ProjectionSteerer(theme_embeddings=themes, alpha=2.0)

        chunks = _make_chunks([[1.0, 2.0, 3.0]])
        steerer.steer(chunks)

        np.testing.assert_allclose(chunks[0].embedding, [1.0, 2.0, 3.0], atol=1e-12)


class TestModuleLoading:
    def test_load_projection_module(self):
        module = load_steerer_module("projection")
        assert hasattr(module, "add_args")
        assert hasattr(module, "create")
        assert hasattr(module, "ProjectionSteerer")

    def test_load_invalid_module_raises(self):
        with pytest.raises(ModuleNotFoundError):
            load_steerer_module("nonexistent_steerer")
