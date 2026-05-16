# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour DeleteDocumentTool."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.mcp.tools.delete_document import DeleteDocumentTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def tool_with_mock(mock_vector_store: AsyncMock) -> DeleteDocumentTool:
    """Tool avec vector store mocke."""
    tool = DeleteDocumentTool(vector_store=mock_vector_store)
    tool._initialized = True
    return tool


class TestDeleteDocumentToolInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert DeleteDocumentTool.name == "delete_document"

    def test_required_fields(self) -> None:
        assert DeleteDocumentTool.input_schema["required"] == ["document_id"]


class TestDeleteDocumentExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_delete_existing_document(
        self,
        tool_with_mock: DeleteDocumentTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.delete_document = AsyncMock(return_value=5)

        result = await tool_with_mock.execute({"document_id": "doc-123"})

        assert result["document_id"] == "doc-123"
        assert result["chunks_deleted"] == 5
        assert result["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(
        self,
        tool_with_mock: DeleteDocumentTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.delete_document = AsyncMock(return_value=0)

        result = await tool_with_mock.execute({"document_id": "nonexistent"})

        assert result["chunks_deleted"] == 0
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_calls_vector_store_delete(
        self,
        tool_with_mock: DeleteDocumentTool,
        mock_vector_store: AsyncMock,
    ) -> None:
        mock_vector_store.delete_document = AsyncMock(return_value=3)

        await tool_with_mock.execute({"document_id": "doc-456"})

        mock_vector_store.delete_document.assert_called_once_with("doc-456")
