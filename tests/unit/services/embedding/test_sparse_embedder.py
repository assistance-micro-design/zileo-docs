# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour SparseEmbedder (BM25 via fastembed)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from src.models.chunk import ChunkMetadata, DocumentChunk
from src.services.embedding.sparse_embedder import SparseEmbedder, SparseEmbeddingData


@dataclass
class FakeSparseEmbedding:
    """Simule un SparseEmbedding fastembed."""

    indices: list[int]
    values: list[float]


@pytest.fixture
def mock_sparse_model() -> MagicMock:
    """Mock du modele SparseTextEmbedding fastembed."""
    model = MagicMock()
    model.embed.return_value = iter(
        [
            FakeSparseEmbedding(indices=[1, 42, 100], values=[0.5, 0.8, 0.3]),
            FakeSparseEmbedding(indices=[7, 42], values=[0.9, 0.1]),
        ]
    )
    model.query_embed.return_value = iter([FakeSparseEmbedding(indices=[1, 42], values=[0.6, 0.7])])
    return model


@pytest.fixture
def sparse_embedder(mock_sparse_model: MagicMock) -> SparseEmbedder:
    """SparseEmbedder avec modele mocke (bypass lazy init)."""
    embedder = SparseEmbedder()
    embedder._model = mock_sparse_model
    return embedder


class TestEmbedQuery:
    """Tests pour embed_query."""

    @pytest.mark.asyncio
    async def test_returns_sparse_data_with_indices_and_values(
        self, sparse_embedder: SparseEmbedder
    ) -> None:
        """embed_query retourne un objet avec indices et values en listes."""
        result = await sparse_embedder.embed_query("securite des donnees")

        assert isinstance(result, SparseEmbeddingData)
        assert isinstance(result.indices, list)
        assert isinstance(result.values, list)
        assert len(result.indices) == len(result.values)
        assert result.indices == [1, 42]
        assert result.values == [0.6, 0.7]

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, sparse_embedder: SparseEmbedder) -> None:
        """Requete vide leve ValueError."""
        with pytest.raises(ValueError, match="vide"):
            await sparse_embedder.embed_query("")

    @pytest.mark.asyncio
    async def test_whitespace_query_raises(self, sparse_embedder: SparseEmbedder) -> None:
        """Requete whitespace-only leve ValueError."""
        with pytest.raises(ValueError, match="vide"):
            await sparse_embedder.embed_query("   ")

    @pytest.mark.asyncio
    async def test_uses_query_embed_not_embed(
        self, sparse_embedder: SparseEmbedder, mock_sparse_model: MagicMock
    ) -> None:
        """embed_query utilise query_embed (optimise requete), pas embed."""
        await sparse_embedder.embed_query("test")

        mock_sparse_model.query_embed.assert_called_once()
        mock_sparse_model.embed.assert_not_called()


class TestEmbedTexts:
    """Tests pour embed_texts (batch)."""

    @pytest.mark.asyncio
    async def test_returns_list_of_sparse_data(self, sparse_embedder: SparseEmbedder) -> None:
        """embed_texts retourne une liste de SparseEmbeddingData."""
        results = await sparse_embedder.embed_texts(["texte 1", "texte 2"])

        assert len(results) == 2
        assert all(isinstance(r, SparseEmbeddingData) for r in results)
        assert results[0].indices == [1, 42, 100]
        assert results[1].values == [0.9, 0.1]

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self, sparse_embedder: SparseEmbedder) -> None:
        """Liste vide retourne liste vide sans appeler le modele."""
        results = await sparse_embedder.embed_texts([])

        assert results == []

    @pytest.mark.asyncio
    async def test_uses_embed_not_query_embed(
        self, sparse_embedder: SparseEmbedder, mock_sparse_model: MagicMock
    ) -> None:
        """embed_texts utilise embed (optimise documents), pas query_embed."""
        await sparse_embedder.embed_texts(["texte"])

        mock_sparse_model.embed.assert_called_once()
        mock_sparse_model.query_embed.assert_not_called()


class TestEmbedChunks:
    """Tests pour embed_chunks (DocumentChunk)."""

    @pytest.mark.asyncio
    async def test_populates_sparse_embedding_on_chunks(
        self, sparse_embedder: SparseEmbedder
    ) -> None:
        """embed_chunks remplit sparse_embedding sur chaque chunk."""
        chunks = [
            DocumentChunk(
                content="Chunk 1",
                metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            ),
            DocumentChunk(
                content="Chunk 2",
                metadata=ChunkMetadata(chunk_id="c2", document_id="d1"),
            ),
        ]

        result = await sparse_embedder.embed_chunks(chunks)

        assert len(result) == 2
        assert result[0].sparse_embedding is not None
        assert result[0].sparse_embedding.indices == [1, 42, 100]
        assert result[1].sparse_embedding is not None
        assert result[1].sparse_embedding.values == [0.9, 0.1]

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self, sparse_embedder: SparseEmbedder) -> None:
        """Liste vide de chunks retourne liste vide."""
        result = await sparse_embedder.embed_chunks([])

        assert result == []


class TestLazyInit:
    """Tests pour l'initialisation lazy du modele."""

    def test_model_not_loaded_at_init(self) -> None:
        """Le modele n'est pas charge au constructeur."""
        embedder = SparseEmbedder()

        assert embedder._model is None

    @pytest.mark.asyncio
    async def test_model_loaded_on_first_call(self) -> None:
        """Le modele est charge au premier appel embed."""
        fake_model = MagicMock()
        fake_model.query_embed.return_value = iter([FakeSparseEmbedding(indices=[1], values=[0.5])])

        mock_fastembed = MagicMock()
        mock_fastembed.SparseTextEmbedding.return_value = fake_model
        with patch.dict(sys.modules, {"fastembed": mock_fastembed}):
            embedder = SparseEmbedder()
            await embedder.embed_query("test")

            mock_fastembed.SparseTextEmbedding.assert_called_once()
            assert embedder._model is not None
