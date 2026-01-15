"""Tests E2E pour le pipeline d'extraction et indexation Word.

Ces tests verifient le fonctionnement de bout en bout pour les documents Word:
- Extraction via WordExtractor
- Conversion vers UnifiedDocument
- Indexation via index_document tool
- Recherche via search_documents tool
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool
from src.mcp.tools.search import SearchDocumentsTool
from src.models.unified import (
    DocumentType,
    ImageData,
    StructuredData,
    TableData,
    UnifiedDocument,
    UnifiedMetadata,
)
from src.services.document.router import DocumentRouter


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_unified_word_doc() -> MagicMock:
    """Mock d'un UnifiedDocument Word."""
    metadata = UnifiedMetadata(
        document_id="word-doc-456",
        filename="rapport.docx",
        file_path="/data/rapport.docx",
        document_type=DocumentType.WORD,
        original_format=".docx",
        page_count=None,
        word_count=500,
        has_tables=True,
        has_images=True,
        title="Rapport Annuel",
        author="Jean Dupont",
    )

    tables = [
        TableData(
            headers=["Mois", "Ventes", "Objectif"],
            rows=[
                ["Janvier", "10000", "12000"],
                ["Février", "15000", "12000"],
                ["Mars", "12000", "12000"],
            ],
        )
    ]

    images = [
        ImageData(
            filename="logo.png",
            content_type="image/png",
            size_kb=45.2,
            has_base64=True,
            alt_text="Logo entreprise",
        )
    ]

    content_markdown = """# Rapport Annuel

## Introduction

Ce document présente les résultats annuels de l'entreprise.

## Résultats

| Mois | Ventes | Objectif |
| --- | --- | --- |
| Janvier | 10000 | 12000 |
| Février | 15000 | 12000 |
| Mars | 12000 | 12000 |

## Conclusion

Les objectifs ont été atteints pour 2 mois sur 3.
"""

    return UnifiedDocument(
        metadata=metadata,
        content_markdown=content_markdown,
        structured_data=StructuredData(tables=tables, images=images),
    )


# =============================================================================
# Tests: Document Router for Word
# =============================================================================


class TestDocumentRouterWord:
    """Tests pour le routing Word."""

    def test_detect_docx_type(self) -> None:
        """Test la detection du type .docx."""
        router = DocumentRouter()
        doc_type = router.detect_type("/path/to/file.docx")
        assert doc_type == DocumentType.WORD

    def test_is_word_supported(self) -> None:
        """Test que l'extension .docx est supportee."""
        router = DocumentRouter()
        assert router.is_supported("file.docx")

    def test_doc_format_not_supported(self) -> None:
        """Test que .doc (ancien format) n'est pas supporté."""
        router = DocumentRouter()
        with pytest.raises(ValueError, match="Format non supporté"):
            router.detect_type("file.doc")


# =============================================================================
# Tests: Index Document Tool for Word
# =============================================================================


class TestIndexDocumentWord:
    """Tests pour l'indexation Word."""

    @pytest.fixture
    def index_tool(self) -> IndexDocumentTool:
        """Instance du tool avec mocks."""
        tool = IndexDocumentTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_index_word_detects_type(
        self,
        index_tool: IndexDocumentTool,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test que l'indexation detecte le type Word."""
        mock_router = MagicMock()
        mock_router.detect_type = MagicMock(return_value=DocumentType.WORD)
        mock_router.extract = AsyncMock(return_value=mock_unified_word_doc)
        mock_router.initialize = AsyncMock()
        index_tool._router = mock_router

        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(side_effect=lambda chunks, **_: chunks)
        index_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.store_unified_chunks = AsyncMock(return_value={"stored_chunks": 1})
        mock_store.initialize = AsyncMock()
        index_tool._vector_store = mock_store

        with patch("pathlib.Path.exists", return_value=True):
            result = await index_tool.execute({"file_path": "/data/rapport.docx"})

        assert result["document_type"] == "word"
        assert result["has_tables"] is True
        assert result["has_images"] is True
        assert result["has_formulas"] is False  # Word n'a pas de formules
        assert result["sheet_names"] is None  # Word n'a pas de feuilles

    @pytest.mark.asyncio
    async def test_index_word_creates_chunks_with_content(
        self,
        index_tool: IndexDocumentTool,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test que l'indexation cree des chunks avec le bon contenu."""
        mock_router = MagicMock()
        mock_router.detect_type = MagicMock(return_value=DocumentType.WORD)
        mock_router.extract = AsyncMock(return_value=mock_unified_word_doc)
        mock_router.initialize = AsyncMock()
        index_tool._router = mock_router

        captured_chunks = []

        async def capture_embed(chunks: list, **_kwargs: dict) -> list:
            captured_chunks.extend(chunks)
            for c in chunks:
                c.embedding = [0.1] * 1024
            return chunks

        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(side_effect=capture_embed)
        index_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.store_unified_chunks = AsyncMock(return_value={"stored_chunks": 1})
        mock_store.initialize = AsyncMock()
        index_tool._vector_store = mock_store

        with patch("pathlib.Path.exists", return_value=True):
            await index_tool.execute({"file_path": "/data/rapport.docx"})

        # Verifier que les chunks contiennent le contenu Word
        assert len(captured_chunks) >= 1
        main_chunk = captured_chunks[0]
        assert "Rapport Annuel" in main_chunk.content
        assert "Introduction" in main_chunk.content


# =============================================================================
# Tests: List Available Documents Tool for Word
# =============================================================================


class TestListAvailableDocumentsWord:
    """Tests pour list_available_documents avec Word."""

    @pytest.fixture
    def list_tool(self) -> ListAvailableDocumentsTool:
        """Instance du tool."""
        tool = ListAvailableDocumentsTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_list_documents_filter_word(
        self,
        list_tool: ListAvailableDocumentsTool,
        tmp_path: Path,
    ) -> None:
        """Test le filtrage par type Word."""
        (tmp_path / "rapport.docx").touch()
        (tmp_path / "memo.docx").touch()
        (tmp_path / "data.xlsx").touch()
        (tmp_path / "guide.pdf").touch()

        list_tool._documents_path = tmp_path

        result = await list_tool.execute({"type_filter": "word"})

        assert result["total_files"] == 2
        assert all(f["type"] == "word" for f in result["files"])
        assert all(f["extension"] == ".docx" for f in result["files"])


# =============================================================================
# Tests: Search Documents with Word
# =============================================================================


class TestSearchDocumentsWord:
    """Tests pour la recherche dans les documents Word."""

    @pytest.fixture
    def search_tool(self) -> SearchDocumentsTool:
        """Instance du tool avec mocks."""
        tool = SearchDocumentsTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_search_with_word_filter(
        self,
        search_tool: SearchDocumentsTool,
    ) -> None:
        """Test la recherche avec filtre document_type=word."""
        mock_results = [
            {
                "chunk_id": "word-chunk-1",
                "document_id": "word-doc-1",
                "content": "Rapport annuel avec résultats positifs",
                "score": 0.91,
                "document_type": "word",
                "has_formula": False,
                "sheet_names": [],
            }
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
        search_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        search_tool._vector_store = mock_store

        result = await search_tool.execute({
            "query": "rapport annuel résultats",
            "filters": {"document_type": "word"},
        })

        assert result["total_results"] == 1
        assert result["results"][0]["document_type"] == "word"
        assert result["results"][0]["has_formula"] is False

    @pytest.mark.asyncio
    async def test_search_word_with_table_filter(
        self,
        search_tool: SearchDocumentsTool,
    ) -> None:
        """Test la recherche Word avec filtre has_table."""
        mock_results = [
            {
                "chunk_id": "word-chunk-table",
                "document_id": "word-doc-1",
                "content": "| Mois | Ventes |\n| --- | --- |",
                "score": 0.85,
                "document_type": "word",
                "has_table": True,
            }
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
        search_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        search_tool._vector_store = mock_store

        result = await search_tool.execute({
            "query": "tableau ventes",
            "filters": {"document_type": "word", "has_table": True},
        })

        assert result["total_results"] == 1


# =============================================================================
# Tests: Integration Pipeline Word
# =============================================================================


class TestWordPipelineIntegration:
    """Tests d'integration du pipeline Word complet."""

    @pytest.mark.asyncio
    async def test_word_extraction_to_unified(
        self,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test la conversion Word vers UnifiedDocument."""
        assert mock_unified_word_doc.document_type == DocumentType.WORD
        assert mock_unified_word_doc.metadata.has_tables is True
        assert mock_unified_word_doc.metadata.has_images is True
        assert mock_unified_word_doc.metadata.has_formulas is False
        assert len(mock_unified_word_doc.structured_data.tables) == 1
        assert len(mock_unified_word_doc.structured_data.images) == 1

    @pytest.mark.asyncio
    async def test_unified_metadata_for_word(
        self,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test les metadonnees Word pour le chunking."""
        base_meta = mock_unified_word_doc.get_chunks_metadata_base()

        assert base_meta["document_type"] == "word"
        assert base_meta["has_formula"] is False
        assert base_meta["has_table"] is True
        assert base_meta["has_image"] is True

    @pytest.mark.asyncio
    async def test_table_data_to_markdown(
        self,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test la conversion tableaux en Markdown."""
        table = mock_unified_word_doc.structured_data.tables[0]
        markdown = table.to_markdown()

        assert "| Mois | Ventes | Objectif |" in markdown
        assert "| Janvier | 10000 | 12000 |" in markdown

    @pytest.mark.asyncio
    async def test_image_data_structure(
        self,
        mock_unified_word_doc: MagicMock,
    ) -> None:
        """Test la structure des donnees image."""
        image = mock_unified_word_doc.structured_data.images[0]

        assert image.filename == "logo.png"
        assert image.content_type == "image/png"
        assert image.has_base64 is True
        assert image.alt_text == "Logo entreprise"


# =============================================================================
# Tests: Cross-format scenarios
# =============================================================================


class TestCrossFormatScenarios:
    """Tests pour scenarios multi-formats."""

    @pytest.fixture
    def search_tool(self) -> SearchDocumentsTool:
        """Instance du tool avec mocks."""
        tool = SearchDocumentsTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_search_across_all_formats(
        self,
        search_tool: SearchDocumentsTool,
    ) -> None:
        """Test la recherche dans tous les formats sans filtre."""
        mock_results = [
            {
                "chunk_id": "pdf-chunk-1",
                "document_id": "pdf-doc-1",
                "content": "PDF content about budget",
                "score": 0.95,
                "document_type": "pdf",
            },
            {
                "chunk_id": "excel-chunk-1",
                "document_id": "excel-doc-1",
                "content": "Excel budget spreadsheet",
                "score": 0.90,
                "document_type": "excel",
                "has_formula": True,
            },
            {
                "chunk_id": "word-chunk-1",
                "document_id": "word-doc-1",
                "content": "Word budget report",
                "score": 0.85,
                "document_type": "word",
            },
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
        search_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        search_tool._vector_store = mock_store

        result = await search_tool.execute({
            "query": "budget",
        })

        assert result["total_results"] == 3

        # Verifier que tous les types sont presents
        types = {r["document_type"] for r in result["results"]}
        assert types == {"pdf", "excel", "word"}

    @pytest.mark.asyncio
    async def test_list_documents_all_formats(
        self,
        tmp_path: Path,
    ) -> None:
        """Test le listing de tous les formats."""
        (tmp_path / "report.pdf").touch()
        (tmp_path / "data.xlsx").touch()
        (tmp_path / "memo.docx").touch()
        (tmp_path / "backup.xls").touch()

        tool = ListAvailableDocumentsTool()
        tool._documents_path = tmp_path
        tool._initialized = True

        result = await tool.execute({"type_filter": "all"})

        assert result["total_files"] == 4
        assert result["by_type"] == {"pdf": 1, "excel": 2, "word": 1}
