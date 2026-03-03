# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le tool MCP EditPresentationTool."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.exceptions import PresentationFileNotFoundError
from src.mcp.tools.edit_presentation import EditPresentationTool
from src.services.presentation.editor import PresentationEditor
from src.services.presentation.generator import PresentationGenerator


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Repertoire de sortie temporaire."""
    output = tmp_path / "output"
    output.mkdir()
    return output


@pytest.fixture
async def sample_pptx(tmp_output: Path) -> str:
    """Cree un fichier pptx de test et retourne le filename."""
    gen = PresentationGenerator(output_path=tmp_output)
    from src.models.api import CreatePresentationParams
    from src.models.presentation_generation import TitleSlideDef

    params = CreatePresentationParams(
        filename="sample.pptx",
        slides=[TitleSlideDef(title="Test")],
    )
    await gen.generate(params)
    return "sample.pptx"


@pytest.fixture
def edit_presentation_tool(tmp_output: Path) -> EditPresentationTool:
    """Tool MCP avec output dans tmp_path."""
    tool = EditPresentationTool()
    tool._initialized = True
    tool._editor = PresentationEditor(output_path=tmp_output)
    return tool


class TestEditPresentationToolInit:
    """Tests initialisation du tool."""

    def test_tool_name(self) -> None:
        assert EditPresentationTool.name == "edit_presentation"

    def test_tool_description(self) -> None:
        assert len(EditPresentationTool.description) > 0

    async def test_do_initialize_sets_input_schema(self, tmp_path: Path) -> None:
        tool = EditPresentationTool()
        tool._editor = PresentationEditor(output_path=tmp_path)
        await tool._do_initialize()
        assert "properties" in EditPresentationTool.input_schema
        assert "filename" in EditPresentationTool.input_schema["properties"]


class TestEditPresentationToolExecute:
    """Tests execution du tool."""

    async def test_execute_update_title(
        self,
        edit_presentation_tool: EditPresentationTool,
        sample_pptx: str,
    ) -> None:
        result = await edit_presentation_tool._do_execute(
            {
                "filename": sample_pptx,
                "operations": [
                    {"op": "update_title", "slide_index": 0, "title": "New Title"},
                ],
            }
        )
        assert result["operations_applied"] == 1
        assert result["operations_skipped"] == 0
        assert result["file_size_bytes"] > 0

    async def test_execute_add_slide(
        self,
        edit_presentation_tool: EditPresentationTool,
        sample_pptx: str,
    ) -> None:
        result = await edit_presentation_tool._do_execute(
            {
                "filename": sample_pptx,
                "operations": [
                    {
                        "op": "add_slide",
                        "slide": {"layout": "title_slide", "title": "Added"},
                    },
                ],
            }
        )
        assert result["operations_applied"] == 1

    async def test_execute_file_not_found(
        self,
        edit_presentation_tool: EditPresentationTool,
    ) -> None:
        with pytest.raises(PresentationFileNotFoundError):
            await edit_presentation_tool._do_execute(
                {
                    "filename": "nonexistent.pptx",
                    "operations": [
                        {"op": "update_title", "slide_index": 0, "title": "T"},
                    ],
                }
            )

    async def test_execute_invalid_filename(
        self,
        edit_presentation_tool: EditPresentationTool,
    ) -> None:
        with pytest.raises(ValidationError):
            await edit_presentation_tool._do_execute(
                {
                    "filename": "test.ppt",
                    "operations": [
                        {"op": "update_title", "slide_index": 0, "title": "T"},
                    ],
                }
            )

    async def test_execute_empty_operations(
        self,
        edit_presentation_tool: EditPresentationTool,
    ) -> None:
        with pytest.raises(ValidationError):
            await edit_presentation_tool._do_execute(
                {
                    "filename": "test.pptx",
                    "operations": [],
                }
            )

    async def test_execute_via_public_execute(
        self,
        edit_presentation_tool: EditPresentationTool,
        sample_pptx: str,
    ) -> None:
        result = await edit_presentation_tool.execute(
            {
                "filename": sample_pptx,
                "operations": [
                    {"op": "update_notes", "slide_index": 0, "notes": "Note text"},
                ],
            }
        )
        assert result["operations_applied"] == 1
