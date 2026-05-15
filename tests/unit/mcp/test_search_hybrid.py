"""Tests unitaires pour SearchHybridTool."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions import EmptyQueryError
from src.mcp.tools.search_hybrid import SearchHybridTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.initialize = AsyncMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return embedder


@pytest.fixture
def mock_sparse_embedder() -> AsyncMock:
    embedder = AsyncMock()
    sparse_data = MagicMock()
    sparse_data.indices = [1, 42]
    sparse_data.values = [0.5, 0.8]
    embedder.embed_query = AsyncMock(return_value=sparse_data)
    return embedder


@pytest.fixture
def search_results() -> list[dict[str, Any]]:
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
def tool_with_mock(
    mock_vector_store: AsyncMock,
    mock_embedder: AsyncMock,
    mock_sparse_embedder: AsyncMock,
    search_results: list[dict[str, Any]],
) -> SearchHybridTool:
    tool = SearchHybridTool(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
    )
    mock_vector_store.search = AsyncMock(return_value=search_results)
    mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
    tool._initialized = True
    return tool


class TestSearchHybridSchema:
    """Tests sur le nom, description et input_schema."""

    def test_tool_name(self) -> None:
        assert SearchHybridTool.name == "search_hybrid"

    def test_description_length(self) -> None:
        assert len(SearchHybridTool.description) <= 200

    def test_description_mentions_hybrid(self) -> None:
        assert "hybrid" in SearchHybridTool.description.lower()

    def test_required_fields(self) -> None:
        assert SearchHybridTool.input_schema["required"] == ["query"]

    def test_input_schema_has_min_cosine_relevance(self) -> None:
        props = SearchHybridTool.input_schema["properties"]
        assert "min_cosine_relevance" in props
        assert props["min_cosine_relevance"]["minimum"] == 0.0
        assert props["min_cosine_relevance"]["maximum"] == 1.0

    def test_input_schema_no_score_threshold(self) -> None:
        props = SearchHybridTool.input_schema["properties"]
        assert "score_threshold" not in props

    def test_input_schema_no_search_mode(self) -> None:
        props = SearchHybridTool.input_schema["properties"]
        assert "search_mode" not in props


class TestSearchHybridExecution:
    """Tests sur l'execution de la recherche hybride."""

    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self, tool_with_mock: SearchHybridTool) -> None:
        result = await tool_with_mock.execute({"query": "comment configurer?"})

        assert result["query"] == "comment configurer?"
        assert result["total_results"] == 1
        assert result["results"][0]["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_search_calls_embedder(
        self,
        tool_with_mock: SearchHybridTool,
        mock_embedder: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test query"})

        mock_embedder.embed_query.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_with_top_k(
        self,
        tool_with_mock: SearchHybridTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "top_k": 10})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert call_kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        tool_with_mock: SearchHybridTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "filters": {"document_id": "doc-123"}})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert call_kwargs["filters"] == {"document_id": "doc-123"}

    @pytest.mark.asyncio
    async def test_empty_query_raises_empty_query_error(
        self, tool_with_mock: SearchHybridTool
    ) -> None:
        with pytest.raises(EmptyQueryError):
            await tool_with_mock.execute({"query": "   "})

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_list(
        self,
        tool_with_mock: SearchHybridTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.hybrid_search = AsyncMock(return_value=[])

        result = await tool_with_mock.execute({"query": "nothing matches"})

        assert result["total_results"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_score_rounded(self, tool_with_mock: SearchHybridTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        assert result["results"][0]["score"] == 0.92

    @pytest.mark.asyncio
    async def test_hybrid_passes_sparse_embedding(
        self,
        tool_with_mock: SearchHybridTool,
        mock_vector_store: AsyncMock,
        mock_sparse_embedder: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "facture 2024-0123"})

        call_kwargs = mock_vector_store.hybrid_search.call_args.kwargs
        assert "sparse_embedding" in call_kwargs
        mock_sparse_embedder.embed_query.assert_called_once_with("facture 2024-0123")

    @pytest.mark.asyncio
    async def test_returns_serializable_dict(self, tool_with_mock: SearchHybridTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        json.dumps(result)


class TestSearchHybridCosineGuard:
    """Tests pour le garde-fou cosinus pre-hybrid."""

    @pytest.mark.asyncio
    async def test_guard_blocks_when_top_cosine_below(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
    ) -> None:
        tool = SearchHybridTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=[])
        mock_vector_store.hybrid_search = AsyncMock(return_value=[])
        tool._initialized = True

        result = await tool.execute({"query": "carbonara", "min_cosine_relevance": 0.72})

        assert result["total_results"] == 0
        assert result["results"] == []
        mock_vector_store.hybrid_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_guard_allows_when_top_cosine_above(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        tool = SearchHybridTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=search_results)
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        await tool.execute({"query": "test", "min_cosine_relevance": 0.72})

        guard_call = mock_vector_store.search.call_args
        assert guard_call.kwargs["top_k"] == 1
        assert guard_call.kwargs["score_threshold"] == 0.72
        mock_vector_store.hybrid_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_guard_propagates_filters(
        self,
        mock_vector_store: AsyncMock,
        mock_embedder: AsyncMock,
        mock_sparse_embedder: AsyncMock,
        search_results: list[dict[str, Any]],
    ) -> None:
        tool = SearchHybridTool(
            vector_store=mock_vector_store,
            embedder=mock_embedder,
            sparse_embedder=mock_sparse_embedder,
        )
        mock_vector_store.search = AsyncMock(return_value=search_results)
        mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
        tool._initialized = True

        filters = {"doc_filename": "guide.pdf"}
        await tool.execute({"query": "test", "min_cosine_relevance": 0.72, "filters": filters})

        guard_call = mock_vector_store.search.call_args
        assert guard_call.kwargs["filters"] == filters

    @pytest.mark.asyncio
    async def test_guard_skipped_when_min_cosine_none(
        self,
        tool_with_mock: SearchHybridTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test"})

        mock_vector_store.search.assert_not_called()
        mock_vector_store.hybrid_search.assert_called_once()
