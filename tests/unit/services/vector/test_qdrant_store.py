"""Tests unitaires pour QdrantVectorStore.

Tests pour find_document_by_filename et initialize,
sans necessiter une instance Qdrant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import VectorStoreConnectionError
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
    """Tests pour hybrid_search avec Qdrant natif (prefetch + FusionQuery)."""

    @pytest.mark.asyncio
    async def test_hybrid_search_uses_prefetch_fusion(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """hybrid_search appelle query_points avec prefetch et FusionQuery."""
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        point = MagicMock()
        point.id = 1
        point.score = 0.85
        point.payload = {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "content": "Result",
            "content_preview": "Result",
            "page_numbers": [1],
            "section_title": None,
            "content_type": "text",
            "doc_filename": "file.pdf",
        }

        response = MagicMock()
        response.points = [point]
        store_with_mock_client.client.query_points = MagicMock(return_value=response)

        sparse_data = SparseEmbeddingData(indices=[1, 42], values=[0.5, 0.8])
        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            sparse_embedding=sparse_data,
            top_k=5,
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-1"

        # Verifier que query_points a ete appele avec prefetch
        call_kwargs = store_with_mock_client.client.query_points.call_args.kwargs
        assert "prefetch" in call_kwargs
        assert len(call_kwargs["prefetch"]) == 2

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_empty_when_no_results(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Pas de resultats retourne une liste vide."""
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        response = MagicMock()
        response.points = []
        store_with_mock_client.client.query_points = MagicMock(return_value=response)

        results = await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            sparse_embedding=SparseEmbeddingData(indices=[1], values=[0.5]),
            top_k=5,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_passes_filters(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Les filtres sont passes a query_points."""
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        response = MagicMock()
        response.points = []
        store_with_mock_client.client.query_points = MagicMock(return_value=response)

        await store_with_mock_client.hybrid_search(
            query_embedding=[0.1] * 1024,
            sparse_embedding=SparseEmbeddingData(indices=[1], values=[0.5]),
            top_k=5,
            filters={"document_id": "doc-1"},
        )

        call_kwargs = store_with_mock_client.client.query_points.call_args.kwargs
        assert call_kwargs["query_filter"] is not None


class TestSemanticSearch:
    """Tests pour search() avec named vector 'dense'."""

    @pytest.mark.asyncio
    async def test_search_uses_dense_named_vector(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """search() passe using='dense' pour named vector."""
        response = MagicMock()
        response.points = []
        store_with_mock_client.client.query_points = MagicMock(return_value=response)

        await store_with_mock_client.search(
            query_embedding=[0.1] * 1024,
            top_k=5,
        )

        call_kwargs = store_with_mock_client.client.query_points.call_args.kwargs
        assert call_kwargs.get("using") == "dense"

    @pytest.mark.asyncio
    async def test_search_returns_results_with_scores(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """search() retourne des resultats avec scores cosine."""
        point = MagicMock()
        point.id = 1
        point.score = 0.82
        point.payload = {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "content": "Semantic result",
            "content_preview": "Semantic",
            "page_numbers": [1],
            "section_title": None,
            "content_type": "text",
            "doc_filename": "file.pdf",
        }

        response = MagicMock()
        response.points = [point]
        store_with_mock_client.client.query_points = MagicMock(return_value=response)

        results = await store_with_mock_client.search(
            query_embedding=[0.1] * 1024,
            top_k=5,
        )

        assert len(results) == 1
        assert results[0]["score"] == 0.82


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


class TestBuildPoints:
    """Tests pour _build_points avec named vectors."""

    def test_builds_named_dense_and_sparse_vectors(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Les points ont un dict de named vectors (dense + sparse)."""
        from src.models.chunk import ChunkMetadata, DocumentChunk
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        chunk = DocumentChunk(
            content="Test content",
            metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            embedding=[0.1] * 1024,
            sparse_embedding=SparseEmbeddingData(indices=[1, 42], values=[0.5, 0.8]),
        )

        points, skipped = store_with_mock_client._build_points(
            [chunk], lambda c: {"content": c.content}
        )

        assert skipped == 0
        assert len(points) == 1
        vector = points[0].vector
        assert isinstance(vector, dict)
        assert "dense" in vector
        assert len(vector["dense"]) == 1024
        assert "sparse" in vector

    def test_skips_chunk_without_dense_embedding(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Chunk sans embedding dense est skippé."""
        from src.models.chunk import ChunkMetadata, DocumentChunk
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        chunk = DocumentChunk(
            content="No embedding",
            metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            embedding=None,
            sparse_embedding=SparseEmbeddingData(indices=[1], values=[0.5]),
        )

        points, skipped = store_with_mock_client._build_points(
            [chunk], lambda c: {"content": c.content}
        )

        assert len(points) == 0
        assert skipped == 1

    def test_skips_chunk_without_sparse_embedding(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Chunk sans sparse embedding est skippé."""
        from src.models.chunk import ChunkMetadata, DocumentChunk

        chunk = DocumentChunk(
            content="Dense only",
            metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            embedding=[0.1] * 1024,
            sparse_embedding=None,
        )

        points, skipped = store_with_mock_client._build_points(
            [chunk], lambda c: {"content": c.content}
        )

        assert len(points) == 0
        assert skipped == 1


class TestCreateCollection:
    """Tests pour _create_collection avec named vectors."""

    @pytest.mark.asyncio
    async def test_creates_collection_with_named_dense_vector(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """La collection utilise un named vector 'dense' de 1024d cosine."""
        await store_with_mock_client._create_collection()

        call_kwargs = store_with_mock_client.client.create_collection.call_args
        vectors_config = call_kwargs.kwargs.get(
            "vectors_config", call_kwargs[1].get("vectors_config")
        )

        # Doit etre un dict de named vectors, pas un VectorParams unnamed
        assert isinstance(vectors_config, dict)
        assert "dense" in vectors_config
        assert vectors_config["dense"].size == 1024

    @pytest.mark.asyncio
    async def test_creates_collection_with_sparse_vectors(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """La collection configure des sparse vectors pour BM25."""
        await store_with_mock_client._create_collection()

        call_kwargs = store_with_mock_client.client.create_collection.call_args
        sparse_config = call_kwargs.kwargs.get(
            "sparse_vectors_config", call_kwargs[1].get("sparse_vectors_config")
        )

        assert sparse_config is not None
        assert "sparse" in sparse_config

    @pytest.mark.asyncio
    async def test_text_index_on_content_for_filtering(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """TEXT index sur 'content' conserve pour filtre text_search."""
        await store_with_mock_client._create_indexes()

        # Verifier qu'un appel cree un TextIndexParams sur "content"
        found_text_index = False
        for call in store_with_mock_client.client.create_payload_index.call_args_list:
            kwargs = call.kwargs if call.kwargs else {}
            field_name = kwargs.get("field_name")
            if field_name == "content":
                found_text_index = True
        assert found_text_index, "TEXT index on 'content' needed for text_search filter"


class TestUpsertPointsErrors:
    """Tests pour la propagation d'erreurs dans _upsert_points."""

    @pytest.mark.asyncio
    async def test_upsert_propagates_exception_from_client(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Une exception client est propagee (VectorStoreConnectionError ou autre)."""
        store_with_mock_client.client.upsert = MagicMock(
            side_effect=VectorStoreConnectionError(host="qdrant", port=6333)
        )

        with pytest.raises(VectorStoreConnectionError):
            await store_with_mock_client._upsert_points([MagicMock()])


class TestFindDocumentByFilenameEdgeCases:
    """Tests pour les branches edge de find_document_by_filename."""

    @pytest.mark.asyncio
    async def test_returns_zero_chunks_when_count_is_empty(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """count.count=0 -> total_chunks=0 dans le resultat."""
        mock_point = MagicMock()
        mock_point.payload = {
            "document_id": "doc-empty",
            "doc_filename": "empty.pdf",
            "doc_file_hash": "h",
            "ingested_at": "2026-01-01T00:00:00+00:00",
        }

        mock_count = MagicMock()
        mock_count.count = 0

        store_with_mock_client.client.scroll = MagicMock(return_value=([mock_point], None))
        store_with_mock_client.client.count = MagicMock(return_value=mock_count)

        result = await store_with_mock_client.find_document_by_filename("empty.pdf")

        assert result is not None
        assert result["total_chunks"] == 0


class TestScrollAllPoints:
    """Tests pour _scroll_all_points (terminaison sur next_offset=None)."""

    @pytest.mark.asyncio
    async def test_scroll_terminates_when_next_offset_none(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Le scroll s'arrete quand next_offset est None."""
        point = MagicMock()
        point.payload = {"document_id": "doc-1"}

        store_with_mock_client.client.scroll = MagicMock(return_value=([point], None))

        result = await store_with_mock_client._scroll_all_points(payload_fields=["document_id"])

        assert len(result) == 1
        assert store_with_mock_client.client.scroll.call_count == 1

    @pytest.mark.asyncio
    async def test_scroll_continues_until_offset_exhausted(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """Le scroll continue tant que next_offset est non-None."""
        p1 = MagicMock()
        p1.payload = {"document_id": "doc-1"}
        p2 = MagicMock()
        p2.payload = {"document_id": "doc-2"}

        store_with_mock_client.client.scroll = MagicMock(
            side_effect=[([p1], "offset-2"), ([p2], None)]
        )

        result = await store_with_mock_client._scroll_all_points(payload_fields=["document_id"])

        assert len(result) == 2
        assert store_with_mock_client.client.scroll.call_count == 2


class TestGetStats:
    """Tests pour get_stats: stats de collection."""

    @pytest.mark.asyncio
    async def test_returns_collection_stats(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """get_stats() retourne points_count, indexed_vectors_count, status."""
        info = MagicMock()
        info.points_count = 100
        info.indexed_vectors_count = 95
        info.status = "green"

        store_with_mock_client.client.get_collection = MagicMock(return_value=info)

        stats = await store_with_mock_client.get_stats()

        assert stats["points_count"] == 100
        assert stats["indexed_vectors_count"] == 95
        assert "green" in stats["status"]


class TestDeleteAndGetChunks:
    """Tests pour delete_document et get_document_chunks."""

    @pytest.mark.asyncio
    async def test_delete_document_returns_one_on_success(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """delete_document() retourne 1 quand le client retourne un status valide."""
        result = MagicMock()
        result.status = "completed"
        store_with_mock_client.client.delete = MagicMock(return_value=result)

        count = await store_with_mock_client.delete_document("doc-1")

        assert count == 1

    @pytest.mark.asyncio
    async def test_get_document_chunks_returns_payloads(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """get_document_chunks() retourne les payloads non vides."""
        p1 = MagicMock()
        p1.payload = {"chunk_id": "c1"}
        p2 = MagicMock()
        p2.payload = None  # filtré

        store_with_mock_client.client.scroll = MagicMock(return_value=([p1, p2], None))

        chunks = await store_with_mock_client.get_document_chunks("doc-1")

        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "c1"


class TestListDocumentsGrouping:
    """Tests pour list_documents et _group_documents_from_points."""

    @pytest.mark.asyncio
    async def test_list_documents_groups_chunks_by_document_id(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """list_documents() agrege les chunks par document_id."""
        p1 = MagicMock()
        p1.payload = {
            "document_id": "doc-a",
            "doc_filename": "a.pdf",
            "doc_total_pages": 5,
        }
        p2 = MagicMock()
        p2.payload = {
            "document_id": "doc-a",
            "doc_filename": "a.pdf",
        }
        p3 = MagicMock()
        p3.payload = None  # ignore

        store_with_mock_client.client.scroll = MagicMock(return_value=([p1, p2, p3], None))

        docs = await store_with_mock_client.list_documents()

        assert len(docs) == 1
        assert docs[0]["document_id"] == "doc-a"
        assert docs[0]["total_chunks"] == 2

    def test_group_documents_skips_points_without_document_id(self) -> None:
        """_group_documents_from_points ignore les points sans document_id."""
        point = MagicMock()
        point.payload = {"doc_filename": "orphan.pdf"}

        result = QdrantVectorStore._group_documents_from_points([point])

        assert result == []


class TestStoreChunksWithMockClient:
    """Tests pour store_chunks et store_unified_chunks (smoke test pipeline)."""

    @pytest.mark.asyncio
    async def test_store_chunks_returns_stats(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """store_chunks() retourne stored_chunks, skipped_chunks, document_id."""
        from datetime import UTC, datetime

        from src.models.chunk import ChunkMetadata, DocumentChunk
        from src.models.document import DocumentMetadata
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        chunk = DocumentChunk(
            content="hello",
            metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            embedding=[0.1] * 1024,
            sparse_embedding=SparseEmbeddingData(indices=[1], values=[0.5]),
        )
        doc_meta = DocumentMetadata(
            document_id="d1",
            file_hash="h",
            filename="f.pdf",
            file_size_bytes=10,
            ingested_at=datetime(2026, 5, 1, tzinfo=UTC),
        )
        store_with_mock_client.client.upsert = MagicMock(return_value=MagicMock(status="ok"))

        stats = await store_with_mock_client.store_chunks([chunk], doc_meta)

        assert stats["stored_chunks"] == 1
        assert stats["skipped_chunks"] == 0
        assert stats["document_id"] == "d1"

    @pytest.mark.asyncio
    async def test_store_unified_chunks_returns_stats(
        self, store_with_mock_client: QdrantVectorStore
    ) -> None:
        """store_unified_chunks() retourne les stats pour un doc Excel/Word."""
        from datetime import UTC, datetime

        from src.models.chunk import ChunkMetadata, DocumentChunk
        from src.models.unified import DocumentType, UnifiedMetadata
        from src.services.embedding.sparse_embedder import SparseEmbeddingData

        chunk = DocumentChunk(
            content="hello",
            metadata=ChunkMetadata(chunk_id="c1", document_id="d1"),
            embedding=[0.1] * 1024,
            sparse_embedding=SparseEmbeddingData(indices=[1], values=[0.5]),
        )
        unified = UnifiedMetadata(
            document_id="d1",
            filename="data.xlsx",
            file_path="/tmp/data.xlsx",
            document_type=DocumentType.EXCEL,
            original_format=".xlsx",
            file_hash="h",
            indexed_at=datetime(2026, 5, 1, tzinfo=UTC),
        )
        store_with_mock_client.client.upsert = MagicMock(return_value=MagicMock(status="ok"))

        stats = await store_with_mock_client.store_unified_chunks([chunk], unified)

        assert stats["stored_chunks"] == 1
        assert stats["document_id"] == "d1"
