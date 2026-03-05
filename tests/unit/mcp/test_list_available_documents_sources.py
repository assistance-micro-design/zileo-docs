"""Tests unitaires pour ListAvailableDocumentsTool — sources generated/templates/images."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool


@pytest.fixture
def tool_with_sources(tmp_path: Path) -> ListAvailableDocumentsTool:
    """Tool avec output, templates, images et documents."""
    # Documents
    docs_path = tmp_path / "documents"
    docs_path.mkdir()
    (docs_path / "rapport.pdf").write_text("fake pdf")
    (docs_path / "data.xlsx").write_text("fake excel")

    output_path = tmp_path / "output"
    output_path.mkdir()
    (output_path / "rapport.xlsx").write_text("fake xlsx")
    (output_path / "presentation.pptx").write_text("fake pptx")
    (output_path / "readme.txt").write_text("ignored")

    # Templates
    templates_path = output_path / "templatesPPTX"
    templates_path.mkdir()
    (templates_path / "corporate.pptx").write_text("fake template")
    (templates_path / "notes.txt").write_text("ignored")

    # Images
    images_path = output_path / "imagesPowerPoint"
    images_path.mkdir()
    (images_path / "logo.png").write_text("fake png")
    (images_path / "photo.jpg").write_text("fake jpg")
    (images_path / "diagram.svg").write_text("fake svg")
    (images_path / "data.csv").write_text("ignored")

    tool = ListAvailableDocumentsTool()
    tool._documents_path = docs_path
    tool._output_path = output_path
    tool._templates_path = templates_path
    tool._images_path = images_path
    tool._initialized = True
    return tool


class TestSourceGenerated:
    """Tests pour source='generated'."""

    @pytest.mark.asyncio
    async def test_source_generated_lists_xlsx_and_pptx(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated"})

        assert result["total_files"] == 2
        filenames = {f["filename"] for f in result["files"]}
        assert "rapport.xlsx" in filenames
        assert "presentation.pptx" in filenames

    @pytest.mark.asyncio
    async def test_source_generated_excludes_templates_dir(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated"})

        filenames = {f["filename"] for f in result["files"]}
        assert "corporate.pptx" not in filenames

    @pytest.mark.asyncio
    async def test_source_generated_excludes_images_dir(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated"})

        filenames = {f["filename"] for f in result["files"]}
        assert "logo.png" not in filenames

    @pytest.mark.asyncio
    async def test_source_generated_filter_excel(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated", "type_filter": "excel"})

        assert result["total_files"] == 1
        assert result["files"][0]["type"] == "excel"

    @pytest.mark.asyncio
    async def test_source_generated_filter_presentation(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute(
            {"source": "generated", "type_filter": "presentation"}
        )

        assert result["total_files"] == 1
        assert result["files"][0]["type"] == "presentation"

    @pytest.mark.asyncio
    async def test_source_generated_editable_with_excel(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "generated", "type_filter": "excel"})

        assert result["files"][0]["editable_with"] == "edit_excel_document"

    @pytest.mark.asyncio
    async def test_source_generated_editable_with_presentation(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute(
            {"source": "generated", "type_filter": "presentation"}
        )

        assert result["files"][0]["editable_with"] == "edit_presentation"

    @pytest.mark.asyncio
    async def test_source_generated_empty_dir(self, tmp_path: Path) -> None:
        output = tmp_path / "empty_output"
        output.mkdir()
        tool = ListAvailableDocumentsTool()
        tool._output_path = output
        tool._templates_path = tmp_path / "tpl"
        tool._images_path = tmp_path / "img"
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


class TestSourceTemplates:
    """Tests pour source='templates'."""

    @pytest.mark.asyncio
    async def test_source_templates_lists_pptx(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "templates"})

        assert result["total_files"] == 1
        assert result["files"][0]["filename"] == "corporate.pptx"
        assert result["files"][0]["type"] == "template"

    @pytest.mark.asyncio
    async def test_source_templates_usable_in_field(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "templates"})

        assert result["files"][0]["usable_in"] == "create_presentation (param: template)"

    @pytest.mark.asyncio
    async def test_source_templates_empty_dir(self, tmp_path: Path) -> None:
        tpl = tmp_path / "empty_tpl"
        tpl.mkdir()
        tool = ListAvailableDocumentsTool()
        tool._templates_path = tpl
        tool._output_path = tmp_path
        tool._images_path = tmp_path
        tool._documents_path = tmp_path
        tool._initialized = True

        result = await tool.execute({"source": "templates"})

        assert result["total_files"] == 0

    @pytest.mark.asyncio
    async def test_source_templates_ignores_non_pptx(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "templates"})

        filenames = {f["filename"] for f in result["files"]}
        assert "notes.txt" not in filenames


class TestSourceImages:
    """Tests pour source='images'."""

    @pytest.mark.asyncio
    async def test_source_images_lists_image_files(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "images"})

        assert result["total_files"] == 3
        types = {f["type"] for f in result["files"]}
        assert types == {"image"}

    @pytest.mark.asyncio
    async def test_source_images_usable_in_field(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "images"})

        for f in result["files"]:
            assert (
                f["usable_in"] == "create_presentation / edit_presentation (param: image.filename)"
            )

    @pytest.mark.asyncio
    async def test_source_images_empty_dir(self, tmp_path: Path) -> None:
        img = tmp_path / "empty_img"
        img.mkdir()
        tool = ListAvailableDocumentsTool()
        tool._images_path = img
        tool._output_path = tmp_path
        tool._templates_path = tmp_path
        tool._documents_path = tmp_path
        tool._initialized = True

        result = await tool.execute({"source": "images"})

        assert result["total_files"] == 0

    @pytest.mark.asyncio
    async def test_source_images_ignores_non_image(
        self, tool_with_sources: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_sources.execute({"source": "images"})

        filenames = {f["filename"] for f in result["files"]}
        assert "data.csv" not in filenames


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
