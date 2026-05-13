"""Tests unitaires pour SearchDocumentsTool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.core.exceptions import EmptyQueryError
from src.mcp.tools.search import SearchDocumentsTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Mock de l'embedder."""
    embedder = AsyncMock()
    embedder.initialize = AsyncMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def search_results() -> list[dict[str, Any]]:
    """Resultats de recherche simules."""
    return [
        {
            "chunk_id": "chunk-001",
            "document_id": "doc-123",
            "content": "Contenu pertinent sur la configuration.",
            "content_preview": "Contenu pertinent",
            "score": 0.92,
            "page_numbers": [1, 2],
            "section_title": "Configuration",
            "content_type": "text",
            "doc_filename": "guide.pdf",
            "document_type": "pdf",
            "has_formula": False,
            "sheet_names": [],
        },
    ]


@pytest.fixture
def mock_sparse_embedder() -> AsyncMock:
    """Mock du sparse embedder BM25."""
    from unittest.mock import MagicMock

    embedder = AsyncMock()
    sparse_data = MagicMock()
    sparse_data.indices = [1, 42]
    sparse_data.values = [0.5, 0.8]
    embedder.embed_query = AsyncMock(return_value=sparse_data)
    return embedder


@pytest.fixture
def tool_with_mock(
    mock_vector_store: AsyncMock,
    mock_embedder: AsyncMock,
    mock_sparse_embedder: AsyncMock,
    search_results: list[dict[str, Any]],
) -> SearchDocumentsTool:
    """Tool avec dependances mockees (mode hybrid par defaut)."""
    tool = SearchDocumentsTool(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
    )
    mock_vector_store.search = AsyncMock(return_value=search_results)
    mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
    tool._initialized = True
    return tool


class TestSearchDocumentsInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert SearchDocumentsTool.name == "search_documents"

    def test_required_fields(self) -> None:
        assert SearchDocumentsTool.input_schema["required"] == ["query"]

    def test_description_length(self) -> None:
        assert len(SearchDocumentsTool.description) <= 200


class TestSearchDocumentsExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_basic_search(self, tool_with_mock: SearchDocumentsTool) -> None:
        result = await tool_with_mock.execute({"query": "comment configurer?"})

        assert result["query"] == "comment configurer?"
        assert result["total_results"] == 1
        assert result["results"][0]["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_search_calls_embedder(
        self,
        tool_with_mock: SearchDocumentsTool,
        mock_embedder: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test query"})

        mock_embedder.embed_query.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_with_top_k(
        self,
        tool_with_mock: SearchDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "top_k": 10})

        call_kwargs = mock_vector_store.hybrid_search.call_args
        assert call_kwargs.kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        tool_with_mock: SearchDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "filters": {"document_id": "doc-123"}})

        call_kwargs = mock_vector_store.hybrid_search.call_args
        assert call_kwargs.kwargs["filters"] == {"document_id": "doc-123"}

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, tool_with_mock: SearchDocumentsTool) -> None:
        with pytest.raises(EmptyQueryError):
            await tool_with_mock.execute({"query": "   "})

    @pytest.mark.asyncio
    async def test_no_results(
        self,
        tool_with_mock: SearchDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.hybrid_search = AsyncMock(return_value=[])

        result = await tool_with_mock.execute({"query": "nothing matches"})

        assert result["total_results"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_score_rounded(self, tool_with_mock: SearchDocumentsTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        score = result["results"][0]["score"]
        assert score == 0.92


class TestSearchModeHybrid:
    """Tests pour le mode de recherche hybride."""

    @pytest.mark.asyncio
    async def test_default_mode_is_hybrid(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """Le mode par defaut est hybrid."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        result = await tool.execute({"query": "test hybride"})

        # hybrid_search doit etre appele, pas search
        mock_vector_store.hybrid_search.assert_called_once()
        assert result["total_results"] == 1

    @pytest.mark.asyncio
    async def test_semantic_mode_uses_dense_only(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """Le mode semantic utilise uniquement la recherche dense."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=search_results)
        tool._initialized = True

        result = await tool.execute({"query": "test semantic", "search_mode": "semantic"})

        # search classique doit etre appele, pas hybrid_search
        mock_vector_store.search.assert_called_once()
        assert result["total_results"] == 1

    @pytest.mark.asyncio
    async def test_hybrid_passes_sparse_embedding(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """Le mode hybrid passe un sparse embedding a hybrid_search."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "facture 2024-0123"})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert "sparse_embedding" in call_kwargs
        mock_sparse_embedder.embed_query.assert_called_once_with("facture 2024-0123")

    def test_input_schema_has_search_mode(self) -> None:
        """Le schema d'input expose search_mode."""
        props = SearchDocumentsTool.input_schema["properties"]
        assert "search_mode" in props
        assert props["search_mode"]["default"] == "hybrid"


class TestScoreThreshold:
    """Tests pour score_threshold opt-in en hybrid + defaut 0.7 en semantic."""

    @pytest.mark.asyncio
    async def test_hybrid_transmits_score_threshold_when_provided(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """Le mode hybrid transmet score_threshold a hybrid_search quand fourni."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "test", "score_threshold": 0.4})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.4

    @pytest.mark.asyncio
    async def test_hybrid_no_threshold_by_default(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """Sans score_threshold, hybrid_search recoit None (pas de filtrage)."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "test"})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert call_kwargs["score_threshold"] is None

    @pytest.mark.asyncio
    async def test_semantic_uses_default_07_when_threshold_omitted(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """En mode semantic sans score_threshold explicite, le defaut 0.7 s'applique."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "test", "search_mode": "semantic"})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_semantic_uses_explicit_threshold_when_provided(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        """En mode semantic avec score_threshold explicite, la valeur est transmise."""
        tool = SearchDocumentsTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "test", "search_mode": "semantic", "score_threshold": 0.85})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.85

    def test_input_schema_score_threshold_has_no_default(self) -> None:
        """score_threshold n'a plus de default dans le schema (opt-in)."""
        props = SearchDocumentsTool.input_schema["properties"]
        assert "default" not in props["score_threshold"]
