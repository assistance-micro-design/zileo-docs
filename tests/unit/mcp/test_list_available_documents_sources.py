"""Tests unitaires pour ListAvailableDocumentsTool — sources generated."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool


@pytest.fixture
def tool_with_sources(tmp_path: Path) -> ListAvailableDocumentsTool:
    """Tool avec output et documents."""
    # Documents
    docs_path = tmp_path / "documents"
    docs_path.mkdir()
    (docs_path / "rapport.pdf").write_text("fake pdf")
    (docs_path / "data.xlsx").write_text("fake excel")

    output_path = tmp_path / "output"
    output_path.mkdir()
    (output_path / "rapport.xlsx").write_text("fake xlsx")
    (output_path / "readme.txt").write_text("ignored")

    tool = ListAvailableDocumentsTool()
    tool._documents_path = docs_path
    tool._output_path = output_path
    tool._initialized = True
    return tool


class TestSourceGenerated:
    """Tests pour source='generated'."""

    @pytest.mark.asyncio
    async def test_source_generated_lists_xlsx(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated"})

        assert result["total_files"] == 1
        filenames = {f["filename"] for f in result["files"]}
        assert "rapport.xlsx" in filenames

    @pytest.mark.asyncio
    async def test_source_generated_filter_excel(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated", "type_filter": "excel"})

        assert result["total_files"] == 1
        assert result["files"][0]["type"] == "excel"

    @pytest.mark.asyncio
    async def test_source_generated_editable_with_excel(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated", "type_filter": "excel"})

        assert result["files"][0]["editable_with"] == "edit_excel_document"

    @pytest.mark.asyncio
    async def test_source_generated_empty_dir(self, tmp_path: Path) -> None:
        output = tmp_path / "empty_output"
        output.mkdir()
        tool = ListAvailableDocumentsTool()
        tool._output_path = output
        tool._documents_path = tmp_path / "docs"
        tool._initialized = True

        result = await tool.execute({"source": "generated"})

        assert result["total_files"] == 0
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_source_generated_path_traversal_blocked(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute(
            {"source": "generated", "subdirectory": "../../../etc"}
        )

        assert result["total_files"] == 0
        assert "error" in result


class TestSourceResponseAndValidation:
    """Tests pour champs response et validation source."""

    @pytest.mark.asyncio
    async def test_response_includes_source_field(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated"})

        assert result["source"] == "generated"

    @pytest.mark.asyncio
    async def test_default_source_is_documents(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({})

        assert result["source"] == "documents"

    @pytest.mark.asyncio
    async def test_invalid_source_raises_error(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        with pytest.raises(Exception, match="source invalide"):
            await tool_with_sources.execute({"source": "invalid"})
