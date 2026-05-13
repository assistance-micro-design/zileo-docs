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


class TestDependencyInjection:
    """Tests pour l'injection de dependances dans IndexDocumentTool."""

    def test_init_with_injected_dependencies(self) -> None:
        """Les instances injectees sont utilisees (pas de creation interne)."""
        mock_vs = MagicMock()
        mock_emb = MagicMock()
        tool = IndexDocumentTool(vector_store=mock_vs, embedder=mock_emb)

        assert tool._vector_store is mock_vs
        assert tool._embedder is mock_emb

    def test_init_without_injection_creates_defaults(self) -> None:
        """Sans injection, les instances sont creees en interne."""
        tool = IndexDocumentTool()

        assert tool._vector_store is not None
        assert tool._embedder is not None
        assert tool._pdf_orchestrator is not None
        assert tool._router is not None

    def test_injected_vector_store_used_for_dedup_check(self) -> None:
        """La verification doublon utilise le vector_store injecte."""
        mock_vs = MagicMock()
        mock_emb = MagicMock()
        tool = IndexDocumentTool(vector_store=mock_vs, embedder=mock_emb)

        # Verifie que c'est bien l'instance injectee
        assert tool._vector_store is mock_vs


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
                "file_hash": "samehash",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"
            mock_path.return_value.suffix = ".pdf"

            with patch(
                "src.mcp.tools.index_document.compute_file_hash",
                return_value="samehash",
            ):
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
                "file_hash": "samehash",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"
            mock_path.return_value.suffix = ".pdf"

            with patch(
                "src.mcp.tools.index_document.compute_file_hash",
                return_value="samehash",
            ):
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
                "file_hash": "samehash",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.name = "rapport.pdf"

            with patch(
                "src.mcp.tools.index_document.compute_file_hash",
                return_value="samehash",
            ):
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

            with patch(
                "src.mcp.tools.index_document.compute_file_hash",
                return_value="newhash",
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/nouveau.pdf"})

        assert "already_indexed" not in result
        assert "document_id" in result
        # Le pipeline PDF a bien ete appele
        tool_with_mocks._pdf_orchestrator.process_and_index.assert_called_once()


class TestFileHashDeduplication:
    """Tests pour la deduplication par hash fichier."""

    @pytest.mark.asyncio
    async def test_same_hash_blocks_reindexation(self, tool_with_mocks: IndexDocumentTool) -> None:
        """Meme filename + meme hash = deja indexe (bloque)."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-id",
                "filename": "data.xlsx",
                "total_chunks": 10,
                "ingested_at": "2026-01-15T10:30:00+00:00",
                "file_hash": "samehash123",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "data.xlsx"
            mock_file.suffix = ".xlsx"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="samehash123"),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/data.xlsx"})

        assert result["already_indexed"] is True

    @pytest.mark.asyncio
    async def test_different_hash_suggests_reindex(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Meme filename + hash different = fichier modifie, propose reindexation."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-id",
                "filename": "data.xlsx",
                "total_chunks": 10,
                "ingested_at": "2026-01-15T10:30:00+00:00",
                "file_hash": "oldhash111",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "data.xlsx"
            mock_file.suffix = ".xlsx"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="newhash222"),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/data.xlsx"})

        assert result["file_modified"] is True
        assert result["document_id"] == "existing-id"
        assert "delete_document" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_stored_hash_falls_back_to_filename_dedup(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Hash vide en base (ancien doc) = dedup par filename seulement."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "old-id",
                "filename": "legacy.pdf",
                "total_chunks": 5,
                "ingested_at": "2025-01-01T00:00:00+00:00",
                "file_hash": "",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "legacy.pdf"
            mock_file.suffix = ".pdf"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="somehash"),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/legacy.pdf"})

        # Hash vide = pas de comparaison possible, on bloque comme avant
        assert result["already_indexed"] is True


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


class TestFileModifiedResponse:
    """Tests pour _build_file_modified_response (hash different)."""

    @pytest.mark.asyncio
    async def test_different_hash_returns_file_modified(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """Quand stored_hash != current_hash, retourne file_modified=True."""
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(
            return_value={
                "document_id": "existing-id",
                "filename": "data.xlsx",
                "total_chunks": 7,
                "ingested_at": "2026-01-01T00:00:00+00:00",
                "file_hash": "OLD_HASH",
            }
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "data.xlsx"
            mock_file.suffix = ".xlsx"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="NEW_HASH"),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/data.xlsx"})

        assert result["file_modified"] is True
        assert result["document_id"] == "existing-id"
        assert "delete_document" in result["message"]


class TestIndexUnifiedExcelAndWord:
    """Tests pour _index_unified (branches Excel et Word)."""

    @pytest.mark.asyncio
    async def test_index_unified_excel_returns_metadata(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """L'indexation Excel route via _router.extract et store_unified_chunks."""
        from src.models.unified import StructuredData, UnifiedDocument, UnifiedMetadata

        metadata = UnifiedMetadata(
            document_id="excel-1",
            filename="data.xlsx",
            file_path="/data/docs/data.xlsx",
            document_type=DocumentType.EXCEL,
            original_format=".xlsx",
            has_tables=True,
            has_formulas=True,
            sheet_names=["Sheet1"],
            title="Donnees",
        )
        unified_doc = UnifiedDocument(
            metadata=metadata,
            content_markdown="contenu Excel",
            structured_data=StructuredData(),
        )

        tool_with_mocks._router.extract = AsyncMock(return_value=unified_doc)
        tool_with_mocks._router.detect_type = MagicMock(return_value=DocumentType.EXCEL)
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(return_value=None)
        tool_with_mocks._vector_store.store_unified_chunks = AsyncMock(
            return_value={"stored_chunks": 1}
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "data.xlsx"
            mock_file.suffix = ".xlsx"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="h"),
                patch(
                    "src.mcp.tools.index_document.embed_dense_and_sparse",
                    AsyncMock(side_effect=lambda chunks, _e, _s: chunks),
                ),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/data.xlsx"})

        assert result["document_type"] == "excel"
        assert result["has_formulas"] is True
        assert result["sheet_names"] == ["Sheet1"]
        tool_with_mocks._vector_store.store_unified_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_unified_word_returns_metadata(
        self, tool_with_mocks: IndexDocumentTool
    ) -> None:
        """L'indexation Word route via _router.extract."""
        from src.models.unified import StructuredData, UnifiedDocument, UnifiedMetadata

        metadata = UnifiedMetadata(
            document_id="word-1",
            filename="doc.docx",
            file_path="/data/docs/doc.docx",
            document_type=DocumentType.WORD,
            original_format=".docx",
            has_tables=False,
            has_images=True,
            word_count=42,
        )
        unified_doc = UnifiedDocument(
            metadata=metadata,
            content_markdown="contenu Word",
            structured_data=StructuredData(),
        )

        tool_with_mocks._router.extract = AsyncMock(return_value=unified_doc)
        tool_with_mocks._router.detect_type = MagicMock(return_value=DocumentType.WORD)
        tool_with_mocks._vector_store.find_document_by_filename = AsyncMock(return_value=None)
        tool_with_mocks._vector_store.store_unified_chunks = AsyncMock(
            return_value={"stored_chunks": 1}
        )

        with patch("src.mcp.tools.index_document.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.name = "doc.docx"
            mock_file.suffix = ".docx"
            mock_file.resolve.return_value = MagicMock()
            mock_file.resolve.return_value.is_relative_to.return_value = True
            mock_path.return_value = mock_file

            with (
                patch("src.mcp.tools.index_document.validate_file_magic", return_value=True),
                patch("src.mcp.tools.index_document.compute_file_hash", return_value="h"),
                patch(
                    "src.mcp.tools.index_document.embed_dense_and_sparse",
                    AsyncMock(side_effect=lambda chunks, _e, _s: chunks),
                ),
            ):
                result = await tool_with_mocks.execute({"file_path": "/data/docs/doc.docx"})

        assert result["document_type"] == "word"
        assert result["has_images"] is True
        assert result["metadata"]["word_count"] == 42


class TestCreateOverflowChunks:
    """Tests pour _create_overflow_chunks (contenu > 8000 chars)."""

    def test_returns_empty_when_content_under_8000(self) -> None:
        """Pas de chunks supplementaires si content_markdown <= 8000 chars."""
        from src.models.unified import StructuredData, UnifiedDocument, UnifiedMetadata

        doc = UnifiedDocument(
            metadata=UnifiedMetadata(
                document_id="d",
                filename="f.xlsx",
                file_path="/tmp/f.xlsx",
                document_type=DocumentType.EXCEL,
                original_format=".xlsx",
            ),
            content_markdown="a" * 500,
            structured_data=StructuredData(),
        )
        tool = IndexDocumentTool()

        assert tool._create_overflow_chunks(doc, start_index=0) == []

    def test_creates_chunks_for_content_over_8000(self) -> None:
        """Au-dela de 8000 chars, des chunks de 4000 sont produits avec overlap."""
        from src.models.unified import StructuredData, UnifiedDocument, UnifiedMetadata

        doc = UnifiedDocument(
            metadata=UnifiedMetadata(
                document_id="d",
                filename="f.xlsx",
                file_path="/tmp/f.xlsx",
                document_type=DocumentType.EXCEL,
                original_format=".xlsx",
            ),
            content_markdown="x" * 20000,
            structured_data=StructuredData(),
        )
        tool = IndexDocumentTool()

        chunks = tool._create_overflow_chunks(doc, start_index=1)

        assert len(chunks) > 1
        assert all(c.metadata.document_id == "d" for c in chunks)
        assert chunks[0].metadata.chunk_index == 1


class TestFormatFormulasForChunk:
    """Tests pour _format_formulas_for_chunk (formules Excel)."""

    def test_empty_formulas_returns_empty_string(self) -> None:
        """Liste vide -> chaine vide."""
        tool = IndexDocumentTool()
        assert tool._format_formulas_for_chunk([]) == ""

    def test_more_than_50_formulas_adds_summary(self) -> None:
        """Au-dela de 50 formules, un suffixe '... et N autres' est ajoute."""
        from src.models.unified import FormulaData

        tool = IndexDocumentTool()
        formulas = [
            FormulaData(cell=f"A{i}", sheet="S1", formula="=1+1", result="2") for i in range(60)
        ]

        result = tool._format_formulas_for_chunk(formulas)

        assert "10 autres formules" in result
