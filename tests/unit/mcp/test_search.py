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
def tool_with_mock(
    mock_vector_store: AsyncMock,
    mock_embedder: AsyncMock,
    search_results: list[dict[str, Any]],
) -> SearchDocumentsTool:
    """Tool avec dependances mockees."""
    tool = SearchDocumentsTool(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
    )
    mock_vector_store.search = AsyncMock(return_value=search_results)
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

        call_kwargs = mock_vector_store.search.call_args
        assert call_kwargs.kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        tool_with_mock: SearchDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute(
            {"query": "test", "filters": {"document_id": "doc-123"}}
        )

        call_kwargs = mock_vector_store.search.call_args
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
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await tool_with_mock.execute({"query": "nothing matches"})

        assert result["total_results"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_score_rounded(self, tool_with_mock: SearchDocumentsTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        score = result["results"][0]["score"]
        assert score == 0.92
