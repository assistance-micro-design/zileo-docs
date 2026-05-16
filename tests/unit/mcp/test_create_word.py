# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour le tool MCP CreateWordTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.tools.create_word import CreateWordTool
from src.services.word.generator import WordGenerator


@pytest.fixture
def create_word_tool(tmp_path: Path) -> CreateWordTool:
    """Tool MCP avec output dans tmp_path."""
    tool = CreateWordTool()
    tool._initialized = True
    tool._generator = WordGenerator(output_path=tmp_path)
    return tool


class TestCreateWordToolInit:
    """Tests initialisation du tool."""

    def test_tool_name(self) -> None:
        """Le tool a le bon nom."""
        assert CreateWordTool.name == "create_word_document"

    def test_tool_description(self) -> None:
        """Le tool a une description non vide."""
        assert len(CreateWordTool.description) > 0

    @pytest.mark.asyncio
    async def test_do_initialize_creates_output_dir(self, tmp_path: Path) -> None:
        """_do_initialize cree le repertoire output."""
        tool = CreateWordTool()
        tool._generator = WordGenerator(output_path=tmp_path / "new_output")
        await tool._do_initialize()
        assert (tmp_path / "new_output").exists()

    @pytest.mark.asyncio
    async def test_do_initialize_sets_input_schema(self, tmp_path: Path) -> None:
        """_do_initialize genere l'input_schema depuis Pydantic."""
        tool = CreateWordTool()
        tool._generator = WordGenerator(output_path=tmp_path)
        await tool._do_initialize()
        assert "properties" in CreateWordTool.input_schema
        assert "filename" in CreateWordTool.input_schema["properties"]
        assert "content" in CreateWordTool.input_schema["properties"]


class TestCreateWordToolExecute:
    """Tests execution du tool."""

    @pytest.mark.asyncio
    async def test_execute_minimal(self, create_word_tool: CreateWordTool) -> None:
        """Execution minimale retourne le bon format."""
        result = await create_word_tool._do_execute(
            {
                "filename": "test.docx",
                "content": "# Hello\n\nWorld",
            }
        )

        assert "file_path" in result
        assert result["filename"] == "test.docx"
        assert result["file_size_bytes"] > 0
        assert result["overwritten"] is False

    @pytest.mark.asyncio
    async def test_execute_with_metadata(self, create_word_tool: CreateWordTool) -> None:
        """Execution avec titre et auteur."""
        result = await create_word_tool._do_execute(
            {
                "filename": "report.docx",
                "content": "# Report\n\nContent here",
                "title": "Monthly Report",
                "author": "Test User",
            }
        )

        assert result["filename"] == "report.docx"
        assert result["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, create_word_tool: CreateWordTool) -> None:
        """Arguments invalides leve une erreur Pydantic."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await create_word_tool._do_execute({"filename": "bad.txt", "content": "test"})
