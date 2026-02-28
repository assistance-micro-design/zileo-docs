"""Tests unitaires pour ListAvailableDocumentsTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool


@pytest.fixture
def tool_with_docs(tmp_path: Path) -> ListAvailableDocumentsTool:
    """Tool avec un dossier temporaire contenant des documents."""
    # Creer des fichiers de test
    (tmp_path / "rapport.pdf").write_text("fake pdf")
    (tmp_path / "data.xlsx").write_text("fake excel")
    (tmp_path / "note.docx").write_text("fake word")
    (tmp_path / "readme.txt").write_text("not supported")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.pdf").write_text("nested pdf")

    tool = ListAvailableDocumentsTool()
    tool._documents_path = tmp_path
    tool._initialized = True
    return tool


@pytest.fixture
def tool_empty(tmp_path: Path) -> ListAvailableDocumentsTool:
    """Tool avec un dossier vide."""
    tool = ListAvailableDocumentsTool()
    tool._documents_path = tmp_path
    tool._initialized = True
    return tool


class TestListAvailableDocumentsInit:
    """Tests pour l'initialisation."""

    def test_tool_name(self) -> None:
        assert ListAvailableDocumentsTool.name == "list_available_documents"

    def test_supported_extensions(self) -> None:
        exts = ListAvailableDocumentsTool.SUPPORTED_EXTENSIONS
        assert ".pdf" in exts
        assert ".xlsx" in exts
        assert ".docx" in exts


class TestListDocumentsExecution:
    """Tests pour l'execution."""

    @pytest.mark.asyncio
    async def test_list_all_documents(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({})

        assert result["total_files"] == 4  # 3 root + 1 nested (recursive)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_filter_by_type_pdf(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({"type_filter": "pdf"})

        assert result["total_files"] == 2  # rapport.pdf + nested.pdf
        assert all(f["type"] == "pdf" for f in result["files"])

    @pytest.mark.asyncio
    async def test_filter_by_type_excel(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({"type_filter": "excel"})

        assert result["total_files"] == 1
        assert result["files"][0]["filename"] == "data.xlsx"

    @pytest.mark.asyncio
    async def test_non_recursive(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({"recursive": False})

        assert result["total_files"] == 3  # Only root files

    @pytest.mark.asyncio
    async def test_subdirectory(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({"subdirectory": "subdir"})

        assert result["total_files"] == 1
        assert result["files"][0]["filename"] == "nested.pdf"

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({"subdirectory": "nonexistent"})

        assert result["total_files"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_directory(self, tool_empty: ListAvailableDocumentsTool) -> None:
        result = await tool_empty.execute({})

        assert result["total_files"] == 0
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_by_type_stats(self, tool_with_docs: ListAvailableDocumentsTool) -> None:
        result = await tool_with_docs.execute({})

        assert "pdf" in result["by_type"]
        assert "excel" in result["by_type"]
        assert "word" in result["by_type"]


class TestPathTraversal:
    """Tests pour la protection anti-traversal."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(
        self, tool_with_docs: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_docs.execute({"subdirectory": "../../../etc"})

        assert result["total_files"] == 0
        assert "error" in result
        assert "within documents directory" in result["error"]

    @pytest.mark.asyncio
    async def test_nested_path_traversal_blocked(
        self, tool_with_docs: ListAvailableDocumentsTool
    ) -> None:
        result = await tool_with_docs.execute({"subdirectory": "subdir/../../../etc"})

        assert result["total_files"] == 0
        assert "error" in result
        assert "within documents directory" in result["error"]
