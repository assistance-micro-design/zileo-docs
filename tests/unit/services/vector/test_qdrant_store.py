"""Tests unitaires pour QdrantVectorStore.

Tests pour find_document_by_filename et initialize,
sans necessiter une instance Qdrant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.vector.qdrant_store import QdrantVectorStore


@pytest.fixture
def store_with_mock_client() -> QdrantVectorStore:
    """QdrantVectorStore avec client Qdrant mocke."""
    with patch("src.services.vector.qdrant_store.QdrantClient"):
        store = QdrantVectorStore()
        store._initialized = True
        return store


class TestFindDocumentByFilename:
    """Tests pour find_document_by_filename."""

    @pytest.mark.asyncio
    async def test_found_returns_document_info(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Retourne les infos si le document existe."""
        mock_point = MagicMock()
        mock_point.payload = {
            "document_id": "doc-123",
            "doc_filename": "rapport.pdf",
            "doc_file_hash": "abc123hash",
            "ingested_at": "2026-01-15T10:30:00+00:00",
        }

        mock_count = MagicMock()
        mock_count.count = 42

        store_with_mock_client.client.scroll = MagicMock(return_value=([mock_point], None))
        store_with_mock_client.client.count = MagicMock(return_value=mock_count)

        result = await store_with_mock_client.find_document_by_filename("rapport.pdf")

        assert result is not None
        assert result["document_id"] == "doc-123"
        assert result["filename"] == "rapport.pdf"
        assert result["total_chunks"] == 42
        assert result["ingested_at"] == "2026-01-15T10:30:00+00:00"
        assert result["file_hash"] == "abc123hash"

    @pytest.mark.asyncio
    async def test_found_returns_empty_hash_when_missing(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Retourne file_hash vide si absent du payload (retro-compat)."""
        mock_point = MagicMock()
        mock_point.payload = {
            "document_id": "doc-old",
            "ingested_at": "",
        }

        mock_count = MagicMock()
        mock_count.count = 5

        store_with_mock_client.client.scroll = MagicMock(return_value=([mock_point], None))
        store_with_mock_client.client.count = MagicMock(return_value=mock_count)

        result = await store_with_mock_client.find_document_by_filename("old.pdf")

        assert result is not None
        assert result["file_hash"] == ""

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, store_with_mock_client: QdrantVectorStore) -> None:
        """Retourne None si le document n'existe pas."""
        store_with_mock_client.client.scroll = MagicMock(return_value=([], None))

        result = await store_with_mock_client.find_document_by_filename("inconnu.pdf")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_payload_returns_none(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Retourne None si le point n'a pas de payload."""
        mock_point = MagicMock()
        mock_point.payload = None

        store_with_mock_client.client.scroll = MagicMock(return_value=([mock_point], None))

        result = await store_with_mock_client.find_document_by_filename("vide.pdf")

        assert result is None

    @pytest.mark.asyncio
    async def test_scroll_uses_filename_filter(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Verifie que le filtre utilise doc_filename avec MatchValue."""
        store_with_mock_client.client.scroll = MagicMock(return_value=([], None))

        await store_with_mock_client.find_document_by_filename("test.xlsx")

        # Verifier que scroll a ete appele avec le bon filtre
        call_kwargs = store_with_mock_client.client.scroll.call_args
        scroll_filter = call_kwargs.kwargs.get("scroll_filter") or call_kwargs[1].get(
            "scroll_filter"
        )

        assert scroll_filter is not None
        assert len(scroll_filter.must) == 1
        condition = scroll_filter.must[0]
        assert condition.key == "doc_filename"
        assert condition.match.value == "test.xlsx"

    @pytest.mark.asyncio
    async def test_count_uses_document_id_filter(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Verifie que le count filtre par document_id."""
        mock_point = MagicMock()
        mock_point.payload = {
            "document_id": "doc-456",
            "ingested_at": "",
        }
        mock_count = MagicMock()
        mock_count.count = 10

        store_with_mock_client.client.scroll = MagicMock(return_value=([mock_point], None))
        store_with_mock_client.client.count = MagicMock(return_value=mock_count)

        await store_with_mock_client.find_document_by_filename("doc.pdf")

        # Verifier que count a ete appele avec le bon document_id
        call_kwargs = store_with_mock_client.client.count.call_args
        count_filter = call_kwargs.kwargs.get("count_filter") or call_kwargs[1].get("count_filter")

        assert count_filter is not None
        condition = count_filter.must[0]
        assert condition.key == "document_id"
        assert condition.match.value == "doc-456"


class TestHybridSearch:
    """Tests pour hybrid_search et _rrf_fusion."""

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_dense_and_text(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Les resultats combinent recherche vectorielle et full-text."""
        # Dense results
        dense_point = MagicMock()
        dense_point.id = 1
        dense_point.score = 0.95
        dense_point.payload = {
            "chunk_id": "chunk-dense",
            "document_id": "doc-1",
            "content": "Dense result",
            "content_preview": "Dense",
            "page_numbers": [1],
            "section_title": "Title",
            "content_type": "text",
            "doc_filename": "file.pdf",
        }

        dense_response = MagicMock()
        dense_response.points = [dense_point]

        # Full-text results
        text_point = MagicMock()
        text_point.id = 2
        text_point.payload = {
            "chunk_id": "chunk-text",
            "document_id": "doc-2",
            "content": "Text result with exact keyword",
            "content_preview": "Text",
            "page_numbers": [3],
            "section_title": "Other",
            "content_type": "text",
            "doc_filename": "other.pdf",
        }

        store_with_mock_client.client.query_points = MagicMock(return_value=dense_response)
        store_with_mock_client.client.scroll = MagicMock(return_value=([text_point], None))

        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            query_text="exact keyword",
            top_k=5,
        )

        # Les deux resultats doivent etre presents
        chunk_ids = {r["chunk_id"] for r in results}
        assert "chunk-dense" in chunk_ids
        assert "chunk-text" in chunk_ids

    @pytest.mark.asyncio
    async def test_hybrid_search_deduplicates_by_chunk_id(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Un chunk present dans les deux recherches n'apparait qu'une fois."""
        shared_payload = {
            "chunk_id": "chunk-shared",
            "document_id": "doc-1",
            "content": "Shared content",
            "content_preview": "Shared",
            "page_numbers": [1],
            "section_title": "Title",
            "content_type": "text",
            "doc_filename": "file.pdf",
        }

        dense_point = MagicMock()
        dense_point.id = 1
        dense_point.score = 0.9
        dense_point.payload = shared_payload

        text_point = MagicMock()
        text_point.id = 1
        text_point.payload = shared_payload

        dense_response = MagicMock()
        dense_response.points = [dense_point]

        store_with_mock_client.client.query_points = MagicMock(return_value=dense_response)
        store_with_mock_client.client.scroll = MagicMock(return_value=([text_point], None))

        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            query_text="shared content",
            top_k=5,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-shared"

    @pytest.mark.asyncio
    async def test_hybrid_search_respects_top_k(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Le nombre de resultats ne depasse pas top_k."""
        points = []
        for i in range(10):
            p = MagicMock()
            p.id = i
            p.score = 0.9 - i * 0.05
            p.payload = {
                "chunk_id": f"chunk-{i}",
                "document_id": "doc-1",
                "content": f"Content {i}",
                "content_preview": f"Preview {i}",
                "page_numbers": [1],
                "section_title": None,
                "content_type": "text",
                "doc_filename": "file.pdf",
            }
            points.append(p)

        dense_response = MagicMock()
        dense_response.points = points

        store_with_mock_client.client.query_points = MagicMock(return_value=dense_response)
        store_with_mock_client.client.scroll = MagicMock(return_value=([], None))

        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            query_text="test",
            top_k=3,
        )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_hybrid_search_no_text_results_falls_back(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Sans resultats full-text, retourne les resultats dense."""
        dense_point = MagicMock()
        dense_point.id = 1
        dense_point.score = 0.85
        dense_point.payload = {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "content": "Dense only",
            "content_preview": "Dense",
            "page_numbers": [],
            "section_title": None,
            "content_type": "text",
            "doc_filename": "file.pdf",
        }

        dense_response = MagicMock()
        dense_response.points = [dense_point]

        store_with_mock_client.client.query_points = MagicMock(return_value=dense_response)
        store_with_mock_client.client.scroll = MagicMock(return_value=([], None))

        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            query_text="no match",
            top_k=5,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-1"

    def test_rrf_fusion_ranking(self, store_with_mock_client: QdrantVectorStore) -> None:
        """RRF favorise les chunks presents dans les deux listes."""
        dense = [
            {"chunk_id": "A", "score": 0.9},
            {"chunk_id": "B", "score": 0.8},
            {"chunk_id": "C", "score": 0.7},
        ]
        text = [
            {"chunk_id": "B", "score": 0.0},  # score inutilise pour RRF
            {"chunk_id": "D", "score": 0.0},
        ]

        fused = store_with_mock_client._rrf_fusion(dense, text, top_k=3, k=60)

        # B devrait etre premier car present dans les deux listes
        assert fused[0]["chunk_id"] == "B"
        assert len(fused) <= 3

    def test_rrf_fusion_empty_lists(self, store_with_mock_client: QdrantVectorStore) -> None:
        """Fusion de listes vides retourne une liste vide."""
        result = store_with_mock_client._rrf_fusion([], [], top_k=5, k=60)
        assert result == []


class TestInitialize:
    """Tests pour initialize."""

    @pytest.mark.asyncio
    async def test_creates_indexes_when_collection_exists(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """_create_indexes() doit etre appele meme si la collection existe deja."""
        store_with_mock_client._initialized = False

        # Collection existe deja
        mock_collections = MagicMock()
        mock_collection = MagicMock()
        mock_collection.name = "documents"
        mock_collections.collections = [mock_collection]
        store_with_mock_client.client.get_collections = MagicMock(return_value=mock_collections)

        with patch.object(
            store_with_mock_client, "_create_indexes", new_callable=AsyncMock
        ) as mock_create_indexes:
            await store_with_mock_client.initialize()

            mock_create_indexes.assert_called_once()
