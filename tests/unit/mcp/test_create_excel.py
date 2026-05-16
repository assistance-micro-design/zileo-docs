# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour le tool MCP CreateExcelTool."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.mcp.tools.create_excel import CreateExcelTool
from src.services.excel.generator import ExcelGenerator


@pytest.fixture
def create_excel_tool(tmp_path: Path) -> CreateExcelTool:
    """Tool MCP avec output dans tmp_path."""
    tool = CreateExcelTool()
    tool._initialized = True
    tool._generator = ExcelGenerator(output_path=tmp_path)
    return tool


class TestCreateExcelToolInit:
    """Tests initialisation du tool."""

    def test_tool_name(self) -> None:
        """Le tool a le bon nom."""
        assert CreateExcelTool.name == "create_excel_document"

    def test_tool_description(self) -> None:
        """Le tool a une description."""
        assert len(CreateExcelTool.description) > 0

    @pytest.mark.asyncio
    async def test_do_initialize_creates_output_dir(self, tmp_path: Path) -> None:
        """_do_initialize cree le repertoire output."""
        tool = CreateExcelTool()
        tool._generator = ExcelGenerator(output_path=tmp_path / "new_output")
        await tool._do_initialize()
        assert (tmp_path / "new_output").exists()

    @pytest.mark.asyncio
    async def test_do_initialize_sets_input_schema(self, tmp_path: Path) -> None:
        """_do_initialize genere l'input_schema."""
        tool = CreateExcelTool()
        tool._generator = ExcelGenerator(output_path=tmp_path)
        await tool._do_initialize()
        assert "properties" in CreateExcelTool.input_schema
        assert "filename" in CreateExcelTool.input_schema["properties"]


class TestCreateExcelToolExecute:
    """Tests execution du tool."""

    @pytest.mark.asyncio
    async def test_execute_minimal(self, create_excel_tool: CreateExcelTool) -> None:
        """Execution minimale retourne le bon format."""
        result = await create_excel_tool._do_execute(
            {
                "filename": "test.xlsx",
                "sheets": [{"name": "Feuille1", "rows": [["A", 1]]}],
            }
        )

        assert "file_path" in result
        assert result["filename"] == "test.xlsx"
        assert result["sheets_created"] == 1
        assert result["total_rows"] == 1
        assert result["total_charts"] == 0
        assert result["file_size_bytes"] > 0
        assert result["overwritten"] is False

    @pytest.mark.asyncio
    async def test_execute_with_all_features(self, create_excel_tool: CreateExcelTool) -> None:
        """Execution avec styles, graphiques et validations."""
        result = await create_excel_tool._do_execute(
            {
                "filename": "full.xlsx",
                "sheets": [
                    {
                        "name": "Data",
                        "headers": ["Cat", "Val"],
                        "rows": [["A", 10], ["B", 20]],
                        "styles": [{"range": "A1:B1", "bold": True}],
                        "charts": [
                            {
                                "type": "bar",
                                "data_range": "B1:B3",
                                "position": "D1",
                            }
                        ],
                        "data_validations": [
                            {"range": "A4:A100", "type": "list", "values": ["A", "B"]}
                        ],
                        "auto_filter": True,
                        "freeze_panes": "A2",
                    }
                ],
                "author": "Test",
            }
        )

        assert result["sheets_created"] == 1
        assert result["total_charts"] == 1
        assert result["total_rows"] == 2

    @pytest.mark.asyncio
    async def test_execute_invalid_filename(self, create_excel_tool: CreateExcelTool) -> None:
        """Filename invalide leve ValidationError."""
        with pytest.raises(ValidationError):
            await create_excel_tool._do_execute(
                {
                    "filename": "test.csv",
                    "sheets": [{"name": "F1"}],
                }
            )

    @pytest.mark.asyncio
    async def test_execute_empty_sheets(self, create_excel_tool: CreateExcelTool) -> None:
        """Liste de feuilles vide leve ValidationError."""
        with pytest.raises(ValidationError):
            await create_excel_tool._do_execute(
                {
                    "filename": "test.xlsx",
                    "sheets": [],
                }
            )

    @pytest.mark.asyncio
    async def test_execute_via_public_execute(self, create_excel_tool: CreateExcelTool) -> None:
        """execute() publique fonctionne (ensure_initialized + _do_execute)."""
        result = await create_excel_tool.execute(
            {
                "filename": "public.xlsx",
                "sheets": [{"name": "S1", "rows": [["data"]]}],
            }
        )
        assert result["filename"] == "public.xlsx"
