# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour SearchSemanticTool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions import EmptyQueryError
from src.mcp.tools.search_semantic import SearchSemanticTool


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
            "content": "Contenu pertinent.",
            "content_preview": "Contenu pertinent",
            "score": 0.85,
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
) -> SearchSemanticTool:
    tool = SearchSemanticTool(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        sparse_embedder=mock_sparse_embedder,
    )
    mock_vector_store.search = AsyncMock(return_value=search_results)
    mock_vector_store.hybrid_search = AsyncMock(return_value=search_results)
    tool._initialized = True
    return tool


class TestSearchSemanticSchema:
    """Tests sur le nom, description et input_schema."""

    def test_tool_name(self) -> None:
        assert SearchSemanticTool.name == "search_semantic"

    def test_description_length(self) -> None:
        assert len(SearchSemanticTool.description) <= 200

    def test_description_mentions_semantic(self) -> None:
        desc = SearchSemanticTool.description.lower()
        assert "cosinus" in desc or "semantic" in desc

    def test_required_fields(self) -> None:
        assert SearchSemanticTool.input_schema["required"] == ["query"]

    def test_input_schema_has_score_threshold(self) -> None:
        props = SearchSemanticTool.input_schema["properties"]
        assert "score_threshold" in props
        assert props["score_threshold"]["minimum"] == 0.0
        assert props["score_threshold"]["maximum"] == 1.0

    def test_input_schema_no_min_cosine_relevance(self) -> None:
        props = SearchSemanticTool.input_schema["properties"]
        assert "min_cosine_relevance" not in props

    def test_input_schema_no_search_mode(self) -> None:
        props = SearchSemanticTool.input_schema["properties"]
        assert "search_mode" not in props


class TestSearchSemanticExecution:
    """Tests sur l'execution de la recherche semantique."""

    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self, tool_with_mock: SearchSemanticTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        assert result["query"] == "test"
        assert result["total_results"] == 1
        assert result["results"][0]["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_no_hybrid_search_called(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test"})

        mock_vector_store.search.assert_called_once()
        mock_vector_store.hybrid_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_calls_embedder(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_embedder: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test query"})

        mock_embedder.embed_query.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_with_top_k(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "top_k": 10})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["top_k"] == 10

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "filters": {"document_id": "doc-123"}})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["filters"] == {"document_id": "doc-123"}

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, tool_with_mock: SearchSemanticTool) -> None:
        with pytest.raises(EmptyQueryError):
            await tool_with_mock.execute({"query": "   "})

    @pytest.mark.asyncio
    async def test_default_threshold_07_when_omitted(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test"})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_explicit_threshold_transmitted(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        await tool_with_mock.execute({"query": "test", "score_threshold": 0.85})

        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.85

    @pytest.mark.asyncio
    async def test_no_results_returns_empty(
        self,
        tool_with_mock: SearchSemanticTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await tool_with_mock.execute({"query": "rien"})

        assert result["total_results"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_score_rounded(self, tool_with_mock: SearchSemanticTool) -> None:
        result = await tool_with_mock.execute({"query": "test"})

        assert result["results"][0]["score"] == 0.85
