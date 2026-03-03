# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le tool MCP CreatePresentationTool."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.mcp.tools.create_presentation import CreatePresentationTool
from src.services.presentation.generator import PresentationGenerator


@pytest.fixture
def create_presentation_tool(tmp_path: Path) -> CreatePresentationTool:
    """Tool MCP avec output dans tmp_path."""
    tool = CreatePresentationTool()
    tool._initialized = True
    tool._generator = PresentationGenerator(
        output_path=tmp_path,
        images_path=tmp_path / "images",
        templates_path=tmp_path / "templates",
    )
    return tool


class TestCreatePresentationToolInit:
    """Tests initialisation du tool."""

    def test_tool_name(self) -> None:
        assert CreatePresentationTool.name == "create_presentation"

    def test_tool_description(self) -> None:
        assert len(CreatePresentationTool.description) > 0

    async def test_do_initialize_creates_output_dir(self, tmp_path: Path) -> None:
        tool = CreatePresentationTool()
        tool._generator = PresentationGenerator(output_path=tmp_path / "new_output")
        await tool._do_initialize()
        assert (tmp_path / "new_output").exists()

    async def test_do_initialize_sets_input_schema(self, tmp_path: Path) -> None:
        tool = CreatePresentationTool()
        tool._generator = PresentationGenerator(output_path=tmp_path)
        await tool._do_initialize()
        assert "properties" in CreatePresentationTool.input_schema
        assert "filename" in CreatePresentationTool.input_schema["properties"]


class TestCreatePresentationToolExecute:
    """Tests execution du tool."""

    async def test_execute_minimal(self, create_presentation_tool: CreatePresentationTool) -> None:
        result = await create_presentation_tool._do_execute(
            {
                "filename": "test.pptx",
                "slides": [{"layout": "title_slide", "title": "Hello"}],
            }
        )

        assert "file_path" in result
        assert result["filename"] == "test.pptx"
        assert result["slides_created"] == 1
        assert result["total_images"] == 0
        assert result["total_charts"] == 0
        assert result["file_size_bytes"] > 0
        assert result["overwritten"] is False

    async def test_execute_with_bullets(
        self, create_presentation_tool: CreatePresentationTool
    ) -> None:
        result = await create_presentation_tool._do_execute(
            {
                "filename": "bullets.pptx",
                "slides": [
                    {
                        "layout": "content_bullets",
                        "title": "Points",
                        "bullets": [
                            {"text": "First"},
                            {"text": "Second", "level": 1},
                        ],
                    }
                ],
            }
        )
        assert result["slides_created"] == 1

    async def test_execute_with_chart(
        self, create_presentation_tool: CreatePresentationTool
    ) -> None:
        result = await create_presentation_tool._do_execute(
            {
                "filename": "chart.pptx",
                "slides": [
                    {
                        "layout": "chart_slide",
                        "title": "Data",
                        "chart": {
                            "chart_type": "bar",
                            "categories": ["A", "B"],
                            "series": [{"name": "S1", "values": [10, 20]}],
                        },
                    }
                ],
            }
        )
        assert result["total_charts"] == 1

    async def test_execute_invalid_filename(
        self, create_presentation_tool: CreatePresentationTool
    ) -> None:
        with pytest.raises(ValidationError):
            await create_presentation_tool._do_execute(
                {
                    "filename": "test.ppt",
                    "slides": [{"layout": "title_slide", "title": "T"}],
                }
            )

    async def test_execute_empty_slides(
        self, create_presentation_tool: CreatePresentationTool
    ) -> None:
        with pytest.raises(ValidationError):
            await create_presentation_tool._do_execute(
                {
                    "filename": "test.pptx",
                    "slides": [],
                }
            )

    async def test_execute_via_public_execute(
        self, create_presentation_tool: CreatePresentationTool
    ) -> None:
        result = await create_presentation_tool.execute(
            {
                "filename": "public.pptx",
                "slides": [{"layout": "title_slide", "title": "Test"}],
            }
        )
        assert result["filename"] == "public.pptx"
