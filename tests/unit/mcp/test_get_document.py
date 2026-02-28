"""Tests unitaires pour GetDocumentTool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.get_document import GetDocumentTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def sample_chunks() -> list[dict[str, Any]]:
    """Chunks de test."""
    return [
        {
            "chunk_id": "chunk-001",
            "chunk_index": 0,
            "content_preview": "Introduction du document",
            "page_numbers": [0],
            "doc_filename": "rapport.pdf",
            "doc_title": "Rapport Test",
            "doc_author": "Auteur Test",
            "doc_total_pages": 5,
            "doc_file_hash": "abc123",
            "section_title": "Introduction",
            "content_type": "text",
            "token_count": 100,
            "has_table": False,
            "has_image": False,
            "ingested_at": "2026-01-15T10:30:00+00:00",
        },
        {
            "chunk_id": "chunk-002",
            "chunk_index": 1,
            "content_preview": "Chapitre 1 avec tableau",
            "page_numbers": [1, 2],
            "doc_filename": "rapport.pdf",
            "doc_title": "Rapport Test",
            "doc_author": "Auteur Test",
            "doc_total_pages": 5,
            "doc_file_hash": "abc123",
            "section_title": "Chapitre 1",
            "content_type": "text",
            "token_count": 150,
            "has_table": True,
            "has_image": False,
            "ingested_at": "2026-01-15T10:30:00+00:00",
        },
    ]


@pytest.fixture
def tool_with_mock(
    mock_vector_store: AsyncMock,
    sample_chunks: list[dict[str, Any]],
) -> GetDocumentTool:
    """Tool avec vector store mocke."""
    tool = GetDocumentTool(vector_store=mock_vector_store)
    mock_vector_store.get_document_chunks = AsyncMock(return_value=sample_chunks)
    tool._initialized = True
    return tool


class TestGetDocumentToolInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert GetDocumentTool.name == "get_document"

    def test_required_fields(self) -> None:
        assert GetDocumentTool.input_schema["required"] == ["document_id"]


class TestGetDocumentExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_returns_document_info(self, tool_with_mock: GetDocumentTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-123"})

        assert result["document_id"] == "doc-123"
        assert result["filename"] == "rapport.pdf"
        assert result["title"] == "Rapport Test"
        assert result["author"] == "Auteur Test"
        assert result["total_pages"] == 5
        assert result["total_chunks"] == 2

    @pytest.mark.asyncio
    async def test_returns_chunks_list(self, tool_with_mock: GetDocumentTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-123"})

        assert len(result["chunks"]) == 2
        assert result["chunks"][0]["chunk_id"] == "chunk-001"
        assert result["chunks"][1]["has_table"] is True

    @pytest.mark.asyncio
    async def test_calculates_total_tokens(self, tool_with_mock: GetDocumentTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-123"})

        assert result["total_tokens"] == 250

    @pytest.mark.asyncio
    async def test_document_not_found(self, mock_vector_store: AsyncMock) -> None:
        mock_vector_store.get_document_chunks = AsyncMock(return_value=[])
        tool = GetDocumentTool(vector_store=mock_vector_store)
        tool._initialized = True

        with pytest.raises(DocumentNotFoundError):
            await tool.execute({"document_id": "nonexistent"})
