# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour ListIndexedDocumentsTool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.mcp.tools.list_indexed_documents import ListIndexedDocumentsTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def tool_with_mock(mock_vector_store: AsyncMock) -> ListIndexedDocumentsTool:
    """Tool avec vector store mocke."""
    tool = ListIndexedDocumentsTool(vector_store=mock_vector_store)
    tool._initialized = True
    return tool


class TestListIndexedDocumentsInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert ListIndexedDocumentsTool.name == "list_indexed_documents"

    def test_no_required_fields(self) -> None:
        assert ListIndexedDocumentsTool.input_schema["required"] == []


class TestListIndexedDocumentsExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_list_documents(
        self,
        tool_with_mock: ListIndexedDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_docs: list[dict[str, Any]] = [
            {"document_id": "doc-1", "filename": "a.pdf", "total_chunks": 10},
            {"document_id": "doc-2", "filename": "b.xlsx", "total_chunks": 5},
        ]
        mock_vector_store.list_documents = AsyncMock(return_value=mock_docs)

        result = await tool_with_mock.execute({})

        assert result["total_documents"] == 2
        assert len(result["documents"]) == 2
        assert result["documents"][0]["document_id"] == "doc-1"

    @pytest.mark.asyncio
    async def test_empty_collection(
        self,
        tool_with_mock: ListIndexedDocumentsTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.list_documents = AsyncMock(return_value=[])

        result = await tool_with_mock.execute({})

        assert result["total_documents"] == 0
        assert result["documents"] == []
