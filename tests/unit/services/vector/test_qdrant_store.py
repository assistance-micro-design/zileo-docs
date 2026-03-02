"""Tests unitaires pour QdrantVectorStore.find_document_by_filename.

Ces tests verifient la detection de documents deja indexes par nom de fichier,
sans necessiter une instance Qdrant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
