"""Tests unitaires pour IndexDocumentTool - path traversal."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.tools.index_document import IndexDocumentTool


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.find_document_by_filename = AsyncMock(return_value=None)
    return store


@pytest.fixture
def tool_with_mocks(mock_vector_store: AsyncMock) -> IndexDocumentTool:
    """Tool avec dependances mockees."""
    tool = IndexDocumentTool()
    tool._vector_store = mock_vector_store
    tool._pdf_orchestrator = AsyncMock()
    tool._router = AsyncMock()
    tool._embedder = AsyncMock()
    tool._initialized = True
    return tool


class TestPathTraversalProtection:
    """Tests pour la protection anti-path-traversal de index_document."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Un chemin hors du dossier documents est rejete."""
        with patch("src.mcp.tools.index_document.settings") as mock_settings:
            mock_settings.DOCUMENTS_PATH = "/app/documents"
            with patch("src.mcp.tools.index_document.Path") as mock_path_cls:
                # file_path resolves outside documents
                mock_file = MagicMock()
                mock_file.resolve.return_value = MagicMock()
                mock_file.resolve.return_value.is_relative_to.return_value = False
                mock_path_cls.return_value = mock_file

                # documents path
                mock_docs = MagicMock()
                mock_docs.resolve.return_value = MagicMock()

                def path_side_effect(arg):
                    if arg == "/app/documents":
                        return mock_docs
                    return mock_file

                mock_path_cls.side_effect = path_side_effect

                result = await tool_with_mocks.execute(
                    {"file_path": "/etc/passwd"}
                )

        assert "error" in result
        assert "within documents directory" in result["error"]

    @pytest.mark.asyncio
    async def test_valid_path_allowed(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Un chemin dans le dossier documents passe la validation."""
        with patch("src.mcp.tools.index_document.settings") as mock_settings:
            mock_settings.DOCUMENTS_PATH = "/app/documents"
            with patch("src.mcp.tools.index_document.Path") as mock_path_cls:
                mock_file = MagicMock()
                mock_file.resolve.return_value = MagicMock()
                mock_file.resolve.return_value.is_relative_to.return_value = True
                mock_file.exists.return_value = False
                mock_file.name = "test.pdf"
                mock_file.__str__ = lambda _self: "/app/documents/test.pdf"

                mock_docs = MagicMock()
                mock_docs.resolve.return_value = MagicMock()

                def path_side_effect(arg):
                    if arg == "/app/documents":
                        return mock_docs
                    return mock_file

                mock_path_cls.side_effect = path_side_effect

                # File doesn't exist -> raises PDFNotFoundError
                from src.core.exceptions import PDFNotFoundError

                with pytest.raises(PDFNotFoundError):
                    await tool_with_mocks.execute(
                        {"file_path": "/app/documents/test.pdf"}
                    )
