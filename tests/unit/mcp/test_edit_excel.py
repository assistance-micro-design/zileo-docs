# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le tool MCP EditExcelTool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.tools.edit_excel import EditExcelTool


class TestEditExcelToolInit:
    """Tests initialisation du tool."""

    def test_name(self) -> None:
        """Nom du tool."""
        assert EditExcelTool.name == "edit_excel_document"

    def test_description_not_empty(self) -> None:
        """Description non vide."""
        assert len(EditExcelTool.description) > 0

    @pytest.mark.asyncio
    async def test_initialize_generates_schema(self) -> None:
        """L'initialisation genere le input_schema."""
        tool = EditExcelTool()
        await tool.initialize()
        assert "properties" in tool.input_schema
        assert "filename" in tool.input_schema["properties"]
        assert "operations" in tool.input_schema["properties"]


class TestEditExcelToolExecute:
    """Tests execution du tool."""

    @pytest.mark.asyncio
    async def test_execute_calls_editor(self) -> None:
        """Execute appelle l'editeur avec les bons params."""
        tool = EditExcelTool()
        tool._initialized = True

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "file_path": "/app/output/test.xlsx",
            "filename": "test.xlsx",
            "operations_applied": 1,
            "operations_skipped": 0,
            "file_size_bytes": 1024,
        }

        with patch.object(
            tool._editor, "edit", new_callable=AsyncMock, return_value=mock_result
        ) as mock_edit:
            result = await tool.execute(
                {
                    "filename": "test.xlsx",
                    "operations": [{"op": "update_cells", "sheet": "S1", "cells": {"A1": 1}}],
                }
            )

        mock_edit.assert_called_once()
        assert result["operations_applied"] == 1

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self) -> None:
        """Execute retourne un dict serializable."""
        tool = EditExcelTool()
        tool._initialized = True

        mock_result = MagicMock()
        mock_result.model_dump.return_value = {
            "file_path": "/test.xlsx",
            "filename": "test.xlsx",
            "operations_applied": 2,
            "operations_skipped": 0,
            "file_size_bytes": 512,
        }

        with patch.object(tool._editor, "edit", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                {
                    "filename": "test.xlsx",
                    "operations": [{"op": "update_cells", "sheet": "S1", "cells": {"A1": 1}}],
                }
            )

        assert isinstance(result, dict)
