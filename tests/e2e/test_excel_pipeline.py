"""Tests E2E pour le pipeline d'extraction et indexation Excel.

Ces tests verifient le fonctionnement de bout en bout pour les documents Excel:
- Extraction via ExcelExtractor
- Conversion vers UnifiedDocument
- Indexation via index_document tool
- Recherche via search_documents tool
- Recuperation des formules via get_excel_formulas tool
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import settings
from src.mcp.tools.get_excel_formulas import GetExcelFormulasTool
from src.mcp.tools.index_document import IndexDocumentTool
from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool
from src.mcp.tools.search import SearchDocumentsTool
from src.models.unified import (
    DocumentType,
    FormulaData,
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
def mock_unified_excel_doc() -> MagicMock:
    """Mock d'un UnifiedDocument Excel."""
    metadata = UnifiedMetadata(
        document_id="excel-doc-123",
        filename="test.xlsx",
        file_path="/app/documents/test.xlsx",
        document_type=DocumentType.EXCEL,
        original_format=".xlsx",
        page_count=2,
        has_tables=True,
        has_formulas=True,
        sheet_names=["Données", "Calculs"],
        title="Test Excel",
        author="Test Author",
    )

    tables = [
        TableData(
            headers=["Produit", "Prix", "Quantité"],
            rows=[["Widget", 10.5, 100], ["Gadget", 20.0, 50]],
            source_location="Feuille: Données",
        )
    ]

    formulas = [
        FormulaData(
            cell="C10",
            sheet="Calculs",
            formula="=SUM(C2:C9)",
            result=150.5,
            dependencies=["C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
        ),
        FormulaData(
            cell="D10",
            sheet="Calculs",
            formula="=AVERAGE(D2:D9)",
            result=75.25,
            dependencies=["D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"],
        ),
    ]

    return UnifiedDocument(
        metadata=metadata,
        content_markdown="# Test Excel\n\n## Données\n\n| Produit | Prix | Quantité |\n| --- | --- | --- |\n| Widget | 10.5 | 100 |\n| Gadget | 20.0 | 50 |",
        structured_data=StructuredData(tables=tables, formulas=formulas),
    )


# =============================================================================
# Tests: Document Router for Excel
# =============================================================================


class TestDocumentRouterExcel:
    """Tests pour le routing Excel."""

    def test_detect_xlsx_type(self) -> None:
        """Test la detection du type .xlsx."""
        router = DocumentRouter()
        doc_type = router.detect_type("/path/to/file.xlsx")
        assert doc_type == DocumentType.EXCEL

    def test_detect_xls_type(self) -> None:
        """Test la detection du type .xls."""
        router = DocumentRouter()
        doc_type = router.detect_type("/path/to/file.xls")
        assert doc_type == DocumentType.EXCEL

    def test_is_excel_supported(self) -> None:
        """Test que les extensions Excel sont supportees."""
        router = DocumentRouter()
        assert router.is_supported("file.xlsx")
        assert router.is_supported("file.xls")

    def test_unsupported_format(self) -> None:
        """Test que les formats non supportes levent une erreur."""
        router = DocumentRouter()
        with pytest.raises(ValueError, match="Format non supporté"):
            router.detect_type("file.csv")


# =============================================================================
# Tests: Index Document Tool for Excel
# =============================================================================


class TestIndexDocumentExcel:
    """Tests pour l'indexation Excel."""

    @pytest.fixture
    def index_tool(self) -> IndexDocumentTool:
        """Instance du tool avec mocks."""
        tool = IndexDocumentTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_index_excel_detects_type(
        self,
        index_tool: IndexDocumentTool,
        mock_unified_excel_doc: MagicMock,
    ) -> None:
        """Test que l'indexation detecte le type Excel."""
        # Mock le router
        mock_router = MagicMock()
        mock_router.detect_type = MagicMock(return_value=DocumentType.EXCEL)
        mock_router.extract = AsyncMock(return_value=mock_unified_excel_doc)
        mock_router.initialize = AsyncMock()
        index_tool._router = mock_router

        # Mock l'embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_chunks = AsyncMock(side_effect=lambda chunks, **_: chunks)
        index_tool._embedder = mock_embedder

        # Mock le vector store
        mock_store = MagicMock()
        mock_store.store_unified_chunks = AsyncMock(return_value={"stored_chunks": 2})
        mock_store.initialize = AsyncMock()
        mock_store.find_document_by_filename = AsyncMock(return_value=None)
        index_tool._vector_store = mock_store

        # Mock file existence + DOCUMENTS_PATH
        with (
            patch.object(settings, "DOCUMENTS_PATH", "/app/documents"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = await index_tool.execute({"file_path": "/app/documents/test.xlsx"})

        assert result["document_type"] == "excel"
        assert result["has_formulas"] is True
        assert result["has_tables"] is True
        assert result["sheet_names"] == ["Données", "Calculs"]

    @pytest.mark.asyncio
    async def test_index_excel_creates_chunks(
        self,
        index_tool: IndexDocumentTool,
        mock_unified_excel_doc: MagicMock,
    ) -> None:
        """Test que l'indexation cree des chunks correctement."""
        mock_router = MagicMock()
        mock_router.detect_type = MagicMock(return_value=DocumentType.EXCEL)
        mock_router.extract = AsyncMock(return_value=mock_unified_excel_doc)
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
        mock_store.store_unified_chunks = AsyncMock(return_value={"stored_chunks": 2})
        mock_store.initialize = AsyncMock()
        mock_store.find_document_by_filename = AsyncMock(return_value=None)
        index_tool._vector_store = mock_store

        with (
            patch.object(settings, "DOCUMENTS_PATH", "/app/documents"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await index_tool.execute({"file_path": "/app/documents/test.xlsx"})

        # Verifier qu'au moins un chunk contient les formules
        assert len(captured_chunks) >= 1
        # Il devrait y avoir un chunk pour les formules si presentes
        assert any(
            c.content_with_context and "Formules Excel" in c.content_with_context
            for c in captured_chunks
        )


# =============================================================================
# Tests: Get Excel Formulas Tool
# =============================================================================


class TestGetExcelFormulasTool:
    """Tests pour le tool get_excel_formulas."""

    @pytest.fixture
    def formulas_tool(self) -> GetExcelFormulasTool:
        """Instance du tool avec mocks."""
        tool = GetExcelFormulasTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_get_formulas_success(
        self,
        formulas_tool: GetExcelFormulasTool,
    ) -> None:
        """Test la recuperation des formules."""
        mock_chunks = [
            {
                "chunk_id": "excel-doc-123_formulas",
                "document_id": "excel-doc-123",
                "document_type": "excel",
                "has_formula": True,
                "content": "# Formules Excel\n\n- **Calculs!C10**: `=SUM(C2:C9)` = 150.5\n- **Calculs!D10**: `=AVERAGE(D2:D9)` = 75.25",
            }
        ]

        mock_store = MagicMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        formulas_tool._vector_store = mock_store

        result = await formulas_tool.execute({"document_id": "excel-doc-123"})

        assert result["document_id"] == "excel-doc-123"
        assert result["total_formulas"] == 2
        assert len(result["formulas"]) == 2

        # Verifier le contenu des formules
        formula_refs = {f["cell"]: f for f in result["formulas"]}
        assert "C10" in formula_refs
        assert formula_refs["C10"]["formula"] == "=SUM(C2:C9)"

    @pytest.mark.asyncio
    async def test_get_formulas_with_sheet_filter(
        self,
        formulas_tool: GetExcelFormulasTool,
    ) -> None:
        """Test le filtrage par feuille."""
        mock_chunks = [
            {
                "chunk_id": "excel-doc-123_formulas",
                "document_type": "excel",
                "has_formula": True,
                "content": "# Formules Excel\n\n- **Données!A10**: `=SUM(A1:A9)`\n- **Calculs!C10**: `=SUM(C2:C9)`",
            }
        ]

        mock_store = MagicMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        formulas_tool._vector_store = mock_store

        result = await formulas_tool.execute(
            {
                "document_id": "excel-doc-123",
                "sheet": "Calculs",
            }
        )

        assert result["total_formulas"] == 1
        assert result["formulas"][0]["sheet"] == "Calculs"

    @pytest.mark.asyncio
    async def test_get_formulas_non_excel_document(
        self,
        formulas_tool: GetExcelFormulasTool,
    ) -> None:
        """Test l'erreur pour un document non-Excel."""
        mock_chunks = [
            {
                "chunk_id": "pdf-doc-456_main",
                "document_type": "pdf",
                "has_formula": False,
                "content": "PDF content",
            }
        ]

        mock_store = MagicMock()
        mock_store.get_document_chunks = AsyncMock(return_value=mock_chunks)
        formulas_tool._vector_store = mock_store

        result = await formulas_tool.execute({"document_id": "pdf-doc-456"})

        assert "error" in result
        assert result["total_formulas"] == 0


# =============================================================================
# Tests: List Available Documents Tool
# =============================================================================


class TestListAvailableDocumentsTool:
    """Tests pour list_available_documents."""

    @pytest.fixture
    def list_tool(self) -> ListAvailableDocumentsTool:
        """Instance du tool."""
        tool = ListAvailableDocumentsTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_list_documents_filter_excel(
        self,
        list_tool: ListAvailableDocumentsTool,
        tmp_path: Path,
    ) -> None:
        """Test le filtrage par type Excel."""
        # Creer des fichiers de test
        (tmp_path / "test.xlsx").touch()
        (tmp_path / "test.xls").touch()
        (tmp_path / "test.pdf").touch()
        (tmp_path / "test.docx").touch()

        list_tool._documents_path = tmp_path

        result = await list_tool.execute({"type_filter": "excel"})

        assert result["total_files"] == 2
        assert all(f["type"] == "excel" for f in result["files"])

    @pytest.mark.asyncio
    async def test_list_documents_all_types(
        self,
        list_tool: ListAvailableDocumentsTool,
        tmp_path: Path,
    ) -> None:
        """Test le listing de tous les types."""
        (tmp_path / "test.xlsx").touch()
        (tmp_path / "test.pdf").touch()
        (tmp_path / "test.docx").touch()

        list_tool._documents_path = tmp_path

        result = await list_tool.execute({"type_filter": "all"})

        assert result["total_files"] == 3
        assert result["by_type"]["excel"] == 1
        assert result["by_type"]["pdf"] == 1
        assert result["by_type"]["word"] == 1


# =============================================================================
# Tests: Search Documents with Excel Filters
# =============================================================================


class TestSearchDocumentsExcel:
    """Tests pour la recherche avec filtres Excel."""

    @pytest.fixture
    def search_tool(self) -> SearchDocumentsTool:
        """Instance du tool avec mocks."""
        tool = SearchDocumentsTool()
        tool._initialized = True
        return tool

    @pytest.mark.asyncio
    async def test_search_with_document_type_filter(
        self,
        search_tool: SearchDocumentsTool,
    ) -> None:
        """Test la recherche avec filtre document_type."""
        mock_results = [
            {
                "chunk_id": "excel-chunk-1",
                "document_id": "excel-doc-1",
                "content": "Excel content about sales",
                "score": 0.92,
                "document_type": "excel",
                "has_formula": True,
                "sheet_names": ["Sales"],
            }
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
        search_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        search_tool._vector_store = mock_store

        result = await search_tool.execute(
            {
                "query": "sales data",
                "filters": {"document_type": "excel"},
            }
        )

        assert result["total_results"] == 1
        assert result["results"][0]["document_type"] == "excel"

    @pytest.mark.asyncio
    async def test_search_with_has_formula_filter(
        self,
        search_tool: SearchDocumentsTool,
    ) -> None:
        """Test la recherche avec filtre has_formula."""
        mock_results = [
            {
                "chunk_id": "excel-formula-chunk",
                "document_id": "excel-doc-1",
                "content": "=SUM(A1:A10) calculates total",
                "score": 0.88,
                "document_type": "excel",
                "has_formula": True,
            }
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
        search_tool._embedder = mock_embedder

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        search_tool._vector_store = mock_store

        result = await search_tool.execute(
            {
                "query": "sum formula",
                "filters": {"has_formula": True},
            }
        )

        assert result["total_results"] == 1
        assert result["results"][0]["has_formula"] is True


# =============================================================================
# Tests: Integration Pipeline Excel
# =============================================================================


class TestExcelPipelineIntegration:
    """Tests d'integration du pipeline Excel complet."""

    @pytest.mark.asyncio
    async def test_excel_extraction_to_unified(
        self,
        mock_unified_excel_doc: MagicMock,
    ) -> None:
        """Test la conversion Excel vers UnifiedDocument."""
        # Verifier les proprietes du document unifie
        assert mock_unified_excel_doc.document_type == DocumentType.EXCEL
        assert mock_unified_excel_doc.metadata.has_formulas is True
        assert mock_unified_excel_doc.metadata.has_tables is True
        assert len(mock_unified_excel_doc.structured_data.formulas) == 2
        assert len(mock_unified_excel_doc.structured_data.tables) == 1

    @pytest.mark.asyncio
    async def test_unified_metadata_for_chunking(
        self,
        mock_unified_excel_doc: MagicMock,
    ) -> None:
        """Test les metadonnees pour le chunking."""
        base_meta = mock_unified_excel_doc.get_chunks_metadata_base()

        assert base_meta["document_type"] == "excel"
        assert base_meta["has_formula"] is True
        assert base_meta["has_table"] is True

    @pytest.mark.asyncio
    async def test_formula_data_to_dict(
        self,
        mock_unified_excel_doc: MagicMock,
    ) -> None:
        """Test la serialisation des formules."""
        formula = mock_unified_excel_doc.structured_data.formulas[0]
        formula_dict = formula.to_dict()

        assert formula_dict["cell"] == "C10"
        assert formula_dict["sheet"] == "Calculs"
        assert formula_dict["formula"] == "=SUM(C2:C9)"
        assert formula_dict["result"] == "150.5"
