"""Tests unitaires pour IndexDocumentTool.

Ces tests verifient:
- La detection de documents deja indexes (guard doublon)
- L'indexation normale quand le document est nouveau
- La description du tool mise a jour
- La protection anti-path-traversal
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.tools.index_document import IndexDocumentTool
from src.models.unified import DocumentType


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Mock du vector store."""
    store = AsyncMock()
    store.initialize = AsyncMock()
    store.find_document_by_filename = AsyncMock(return_value=None)
    store.store_unified_chunks = AsyncMock(return_value={"stored_chunks": 5})
    return store


@pytest.fixture
def mock_pdf_orchestrator() -> AsyncMock:
    """Mock du pipeline PDF."""
    orchestrator = AsyncMock()
    orchestrator.initialize = AsyncMock()

    # Creer un mock de ProcessingResult
    mock_result = MagicMock()
    mock_result.analysis.metadata.document_id = "new-pdf-doc-id"
    mock_result.analysis.metadata.filename = "rapport.pdf"
    mock_result.analysis.metadata.total_pages = 10
    mock_result.analysis.metadata.title = "Rapport"
    mock_result.analysis.metadata.author = "Auteur"
    mock_result.analysis.metadata.creation_date = None
    mock_result.pages_processed_native = 8
    mock_result.pages_processed_ocr = 2
    mock_result.chunks_stored = 42
    mock_result.chunks = []
    mock_result.errors = []

    orchestrator.process_and_index = AsyncMock(return_value=mock_result)
    return orchestrator


@pytest.fixture
def mock_router() -> AsyncMock:
    """Mock du document router."""
    router = AsyncMock()
    router.initialize = AsyncMock()
    return router


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """Mock de l'embedder."""
    embedder = AsyncMock()
    embedder.initialize = AsyncMock()
    return embedder


@pytest.fixture
def tool_with_mocks(
    mock_vector_store: AsyncMock,
    mock_pdf_orchestrator: AsyncMock,
    mock_router: AsyncMock,
    mock_embedder: AsyncMock,
) -> IndexDocumentTool:
    """Tool avec toutes les dependances mockees."""
    tool = IndexDocumentTool()
    tool._vector_store = mock_vector_store
    tool._pdf_orchestrator = mock_pdf_orchestrator
    tool._router = mock_router
    tool._embedder = mock_embedder
    tool._initialized = True
    return tool


class TestIndexDocumentToolDescription:
    """Tests pour la description du tool."""

    def test_description_mentions_already_indexed(self) -> None:
        """La description previent le LLM du comportement doublon."""
        assert "deja indexe" in IndexDocumentTool.description

    def test_description_length_under_limit(self) -> None:
        """La description ne depasse pas 200 caracteres."""
        assert len(IndexDocumentTool.description) <= 200


class TestDuplicateIndexationGuard:
    """Tests pour la protection contre la double indexation."""

    @pytest.mark.asyncio
    async def test_already_indexed_returns_existing(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Si le fichier est deja indexe, retourne l'ID existant."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-doc-id",
                "filename": "rapport.pdf",
                "total_chunks": 42,
                "ingested_at": "2026-01-15T10:30:00+00:00",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"
            mock_path.return_value.suffix = ".pdf"

            result = await tool_with_mocks.execute({"file_path": "/data/docs/rapport.pdf"})

        assert result["already_indexed"] is True
        assert result["document_id"] == "existing-doc-id"
        assert result["total_chunks"] == 42
        assert result["filename"] == "rapport.pdf"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_already_indexed_skips_pipeline(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Le pipeline n'est PAS execute si le document est deja indexe."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-doc-id",
                "filename": "rapport.pdf",
                "total_chunks": 42,
                "ingested_at": "2026-01-15T10:30:00+00:00",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"
            mock_path.return_value.suffix = ".pdf"

            await tool_with_mocks.execute({"file_path": "/data/docs/rapport.pdf"})

        # Le pipeline PDF ne doit PAS avoir ete appele
        tool_with_mocks._pdf_orchestrator.process_and_index.assert_not_called()
        # Le router ne doit PAS avoir ete appele (on sort avant)
        tool_with_mocks._router.detect_type.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_indexed_message_guides_llm(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Le message guide le LLM vers search_documents et delete_document."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-doc-id",
                "filename": "rapport.pdf",
                "total_chunks": 42,
                "ingested_at": "2026-01-15T10:30:00+00:00",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"

            result = await tool_with_mocks.execute({"file_path": "/data/docs/rapport.pdf"})

        assert "search_documents" in result["message"]
        assert "delete_document" in result["message"]

    @pytest.mark.asyncio
    async def test_new_file_has_no_already_indexed_flag(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Un nouveau fichier n'a pas le champ already_indexed."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(return_value=None)
        tool_with_mocks._router.detect_type = MagicMock(return_value=DocumentType.PDF)

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "nouveau.pdf"
            mock_path.return_value.suffix = ".pdf"
            mock_path.return_value.__str__ = lambda _self: "/data/docs/nouveau.pdf"

            result = await tool_with_mocks.execute({"file_path": "/data/docs/nouveau.pdf"})

        assert "already_indexed" not in result
        assert "document_id" in result
        # Le pipeline PDF a bien ete appele
        tool_with_mocks._pdf_orchestrator.process_and_index.assert_called_once()


class TestPathTraversalProtection:
    """Tests pour la protection anti-path-traversal de index_document."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Un chemin hors du dossier documents est rejete."""
        with patch("src.mcp.tools.index_document.settings") as mock_settings:
            mock_settings.DOCUMENTS_PATH = "/app/documents"
            with patch("src.mcp.tools.index_document.Path") as mock_path_cls:
                mock_file = MagicMock()
                mock_file.resolve.return_value = MagicMock()
                mock_file.resolve.return_value.is_relative_to.return_value = False
                mock_path_cls.return_value = mock_file

                mock_docs = MagicMock()
                mock_docs.resolve.return_value = MagicMock()

                def path_side_effect(arg):  # type: ignore[no-untyped-def]
                    if arg == "/app/documents":
                        return mock_docs
                    return mock_file

                mock_path_cls.side_effect = path_side_effect

                result = await tool_with_mocks.execute({"file_path": "/etc/passwd"})

        assert "error" in result
        assert "within documents directory" in result["error"]

    @pytest.mark.asyncio
    async def test_valid_path_allowed(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Un chemin dans le dossier documents passe la validation."""
        from src.core.exceptions import SourceFileNotFoundError

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

                def path_side_effect(arg):  # type: ignore[no-untyped-def]
                    if arg == "/app/documents":
                        return mock_docs
                    return mock_file

                mock_path_cls.side_effect = path_side_effect

                with pytest.raises(SourceFileNotFoundError):
                    await tool_with_mocks.execute({"file_path": "/app/documents/test.pdf"})
