# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour GetExcelFormulasTool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.get_excel_formulas import GetExcelFormulasTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    return store


@pytest.fixture
def excel_chunks() -> list[dict[str, Any]]:
    """Chunks d'un document Excel avec formules."""
    return [
        {
            "chunk_id": "doc-excel_main",
            "chunk_index": 0,
            "content": "# Donnees\n\nContenu du tableau principal.",
            "document_type": "excel",
            "has_formula": False,
        },
        {
            "chunk_id": "doc-excel_formulas",
            "chunk_index": 1,
            "content": (
                "# Formules Excel\n\n"
                "- **Sheet1!A1**: `=SUM(B1:B10)` = 100\n"
                "- **Sheet1!C1**: `=AVERAGE(B1:B10)` = 10\n"
                "- **Sheet2!A1**: `=VLOOKUP(A1,Sheet1!A:B,2,FALSE)`\n"
            ),
            "document_type": "excel",
            "has_formula": True,
        },
    ]


@pytest.fixture
def tool_with_mock(
    mock_vector_store: AsyncMock,
    excel_chunks: list[dict[str, Any]],
) -> GetExcelFormulasTool:
    """Tool avec vector store mocke."""
    tool = GetExcelFormulasTool(vector_store=mock_vector_store)
    mock_vector_store.get_document_chunks = AsyncMock(return_value=excel_chunks)
    tool._initialized = True
    return tool


class TestGetExcelFormulasInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert GetExcelFormulasTool.name == "get_excel_formulas"

    def test_required_fields(self) -> None:
        assert GetExcelFormulasTool.input_schema["required"] == ["document_id"]


class TestGetExcelFormulasExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_returns_formulas(self, tool_with_mock: GetExcelFormulasTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-excel"})

        assert result["total_formulas"] == 3
        assert result["formulas"][0]["formula"] == "=SUM(B1:B10)"
        assert result["formulas"][0]["result"] == "100"

    @pytest.mark.asyncio
    async def test_filter_by_sheet(self, tool_with_mock: GetExcelFormulasTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-excel", "sheet": "Sheet2"})

        assert result["total_formulas"] == 1
        assert result["formulas"][0]["sheet"] == "Sheet2"

    @pytest.mark.asyncio
    async def test_filter_by_cell_range(self, tool_with_mock: GetExcelFormulasTool) -> None:
        result = await tool_with_mock.execute({"document_id": "doc-excel", "cell_range": "A1:A10"})

        # Only A1 cells match
        assert all(f["cell"] == "A1" for f in result["formulas"])

    @pytest.mark.asyncio
    async def test_document_not_found(self, mock_vector_store: AsyncMock) -> None:
        mock_vector_store.get_document_chunks = AsyncMock(return_value=[])
        tool = GetExcelFormulasTool(vector_store=mock_vector_store)
        tool._initialized = True

        with pytest.raises(DocumentNotFoundError):
            await tool.execute({"document_id": "nonexistent"})

    @pytest.mark.asyncio
    async def test_non_excel_document(self, mock_vector_store: AsyncMock) -> None:
        pdf_chunks = [
            {"chunk_id": "c1", "document_type": "pdf", "has_formula": False, "content": "text"},
        ]
        mock_vector_store.get_document_chunks = AsyncMock(return_value=pdf_chunks)
        tool = GetExcelFormulasTool(vector_store=mock_vector_store)
        tool._initialized = True

        result = await tool.execute({"document_id": "doc-pdf"})

        assert result["total_formulas"] == 0
        assert "error" in result
