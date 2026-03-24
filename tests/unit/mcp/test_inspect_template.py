# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour le tool MCP InspectTemplateTool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.mcp.tools.inspect_template import InspectTemplateTool
from src.models.api import InspectTemplateParams
from src.services.inspection.template_inspector import TemplateInspector


@pytest.fixture
def inspect_template_tool(tmp_path: Path) -> InspectTemplateTool:
    """Tool MCP avec templates dans tmp_path."""
    tool = InspectTemplateTool()
    tool._initialized = True
    tool._inspector = TemplateInspector(templates_path=tmp_path / "templates")
    return tool


class TestInspectTemplateToolInit:
    """Tests initialisation du tool."""

    def test_tool_name(self) -> None:
        assert InspectTemplateTool.name == "inspect_template"

    def test_tool_description(self) -> None:
        assert len(InspectTemplateTool.description) > 0

    @pytest.mark.asyncio
    async def test_do_initialize_sets_input_schema(self, tmp_path: Path) -> None:
        tool = InspectTemplateTool()
        tool._inspector = TemplateInspector(templates_path=tmp_path)
        await tool._do_initialize()
        assert "properties" in InspectTemplateTool.input_schema
        assert "template" in InspectTemplateTool.input_schema["properties"]


class TestInspectTemplateToolExecute:
    """Tests execution du tool."""

    @pytest.mark.asyncio
    async def test_execute_returns_inspection_result(
        self, inspect_template_tool: InspectTemplateTool
    ) -> None:
        mock_result = {
            "template": "test.pptx",
            "file_size_bytes": 1000,
            "slide_width_cm": 33.87,
            "slide_height_cm": 19.05,
            "theme": {"name": None},
            "total_layouts": 1,
            "layouts": [{"index": 0, "name": "Blank", "placeholders": []}],
            "existing_slides_count": 0,
            "hint": "Ce template a 1 layouts.",
        }
        with patch.object(
            inspect_template_tool._inspector,
            "inspect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await inspect_template_tool._do_execute({"template": "test.pptx"})

        assert result["template"] == "test.pptx"
        assert result["total_layouts"] == 1

    @pytest.mark.asyncio
    async def test_execute_validates_params(
        self, inspect_template_tool: InspectTemplateTool
    ) -> None:
        with pytest.raises(ValidationError):
            await inspect_template_tool._do_execute({"template": ""})


class TestInspectTemplateParams:
    """Tests du model InspectTemplateParams."""

    def test_valid(self) -> None:
        params = InspectTemplateParams(template="corporate.pptx")
        assert params.template == "corporate.pptx"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            InspectTemplateParams(template="")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError):
            InspectTemplateParams(template="a" * 256)
