# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour les modèles unifiés multi-format."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.models.chunk import ChunkMetadata
from src.models.unified import (
    DocumentType,
    FormulaData,
    StructuredData,
    UnifiedDocument,
    UnifiedImageData,
    UnifiedMetadata,
    UnifiedTableData,
)
from src.services.document.router import DocumentRouter


class TestDocumentType:
    """Tests pour DocumentType enum."""

    def test_pdf_value(self) -> None:
        assert DocumentType.PDF.value == "pdf"

    def test_excel_value(self) -> None:
        assert DocumentType.EXCEL.value == "excel"

    def test_word_value(self) -> None:
        assert DocumentType.WORD.value == "word"

    def test_enum_is_str(self) -> None:
        """DocumentType hérite de str pour sérialisation JSON."""
        assert isinstance(DocumentType.PDF, str)
        assert DocumentType.PDF == "pdf"


class TestUnifiedTableData:
    """Tests pour UnifiedTableData."""

    def test_to_markdown_with_headers(self) -> None:
        table = UnifiedTableData(
            headers=["A", "B", "C"],
            rows=[
                [1, 2, 3],
                [4, 5, 6],
            ],
        )

        md = table.to_markdown()

        assert "| A | B | C |" in md
        assert "| --- | --- | --- |" in md
        assert "| 1 | 2 | 3 |" in md
        assert "| 4 | 5 | 6 |" in md

    def test_to_markdown_without_headers(self) -> None:
        """Auto-génère des headers si non fournis."""
        table = UnifiedTableData(
            rows=[[1, 2], [3, 4]],
        )

        md = table.to_markdown()

        assert "| Col1 | Col2 |" in md

    def test_to_markdown_empty(self) -> None:
        table = UnifiedTableData()
        assert table.to_markdown() == ""

    def test_to_markdown_with_none_values(self) -> None:
        """Les valeurs None sont converties en chaînes vides."""
        table = UnifiedTableData(
            headers=["X", "Y"],
            rows=[[1, None], [None, 2]],
        )

        md = table.to_markdown()

        assert "| 1 |  |" in md
        assert "|  | 2 |" in md

    def test_to_dict(self) -> None:
        table = UnifiedTableData(
            headers=["X"],
            rows=[[1], [None]],
            source_location="Sheet1",
        )

        d = table.to_dict()

        assert d["headers"] == ["X"]
        assert d["rows"] == [["1"], [""]]
        assert d["source_location"] == "Sheet1"

    def test_to_dict_none_location(self) -> None:
        table = UnifiedTableData(headers=["A"], rows=[[1]])
        d = table.to_dict()
        assert d["source_location"] is None


class TestFormulaData:
    """Tests pour FormulaData."""

    def test_creation(self) -> None:
        formula = FormulaData(
            cell="C10",
            sheet="Données",
            formula="=SUM(C2:C9)",
            result=1500.0,
            dependencies=["C2", "C9"],
        )

        assert formula.cell == "C10"
        assert formula.sheet == "Données"
        assert formula.formula == "=SUM(C2:C9)"
        assert formula.result == 1500.0
        assert formula.dependencies == ["C2", "C9"]

    def test_to_dict(self) -> None:
        formula = FormulaData(
            cell="C10",
            sheet="Données",
            formula="=SUM(C2:C9)",
            result=1500.0,
            dependencies=["C2", "C9"],
        )

        d = formula.to_dict()

        assert d["cell"] == "C10"
        assert d["sheet"] == "Données"
        assert d["formula"] == "=SUM(C2:C9)"
        assert d["result"] == "1500.0"
        assert d["dependencies"] == ["C2", "C9"]

    def test_to_dict_none_result(self) -> None:
        formula = FormulaData(
            cell="A1",
            sheet="Data",
            formula="=B1+C1",
        )

        d = formula.to_dict()

        assert d["result"] is None

    def test_default_dependencies(self) -> None:
        formula = FormulaData(
            cell="A1",
            sheet="Data",
            formula="=1+1",
        )

        assert formula.dependencies == []


class TestUnifiedImageData:
    """Tests pour UnifiedImageData."""

    def test_creation(self) -> None:
        image = UnifiedImageData(
            filename="logo.png",
            content_type="image/png",
            size_kb=150.5,
            has_base64=True,
            alt_text="Company logo",
            source_location="Page 1",
        )

        assert image.filename == "logo.png"
        assert image.content_type == "image/png"
        assert image.size_kb == 150.5
        assert image.has_base64 is True
        assert image.alt_text == "Company logo"
        assert image.source_location == "Page 1"

    def test_defaults(self) -> None:
        image = UnifiedImageData(
            filename="test.jpg",
            content_type="image/jpeg",
            size_kb=100.0,
        )

        assert image.has_base64 is False
        assert image.alt_text is None
        assert image.source_location is None


class TestStructuredData:
    """Tests pour StructuredData."""

    def test_empty_defaults(self) -> None:
        data = StructuredData()

        assert data.tables == []
        assert data.formulas == []
        assert data.images == []

    def test_counts(self) -> None:
        data = StructuredData(
            tables=[UnifiedTableData(headers=["A"])],
            formulas=[
                FormulaData(cell="A1", sheet="S1", formula="=1"),
                FormulaData(cell="A2", sheet="S1", formula="=2"),
            ],
            images=[
                UnifiedImageData(filename="a.png", content_type="image/png", size_kb=10),
            ],
        )

        assert data.tables_count == 1
        assert data.formulas_count == 2
        assert data.images_count == 1

    def test_to_dict(self) -> None:
        data = StructuredData(
            tables=[UnifiedTableData(headers=["X"], rows=[[1]])],
            formulas=[FormulaData(cell="B1", sheet="Data", formula="=A1*2", result=10)],
        )

        d = data.to_dict()

        assert len(d["tables"]) == 1
        assert len(d["formulas"]) == 1
        assert d["images_count"] == 0


class TestUnifiedMetadata:
    """Tests pour UnifiedMetadata."""

    def test_required_fields(self) -> None:
        meta = UnifiedMetadata(
            filename="test.xlsx",
            file_path="/path/test.xlsx",
            document_type=DocumentType.EXCEL,
            original_format=".xlsx",
        )

        assert meta.filename == "test.xlsx"
        assert meta.file_path == "/path/test.xlsx"
        assert meta.document_type == DocumentType.EXCEL
        assert meta.original_format == ".xlsx"

    def test_auto_generated_document_id(self) -> None:
        meta = UnifiedMetadata(
            filename="test.pdf",
            file_path="/path/test.pdf",
            document_type=DocumentType.PDF,
            original_format=".pdf",
        )

        assert meta.document_id is not None
        assert len(meta.document_id) == 36  # UUID format

    def test_defaults(self) -> None:
        meta = UnifiedMetadata(
            filename="test.pdf",
            file_path="/path/test.pdf",
            document_type=DocumentType.PDF,
            original_format=".pdf",
        )

        assert meta.file_size_bytes == 0
        assert meta.page_count is None
        assert meta.word_count == 0
        assert meta.char_count == 0
        assert meta.has_tables is False
        assert meta.has_images is False
        assert meta.has_formulas is False
        assert meta.has_ocr_content is False
        assert meta.title is None
        assert meta.author is None
        assert meta.sheet_names == []
        assert meta.indexed_at is not None

    def test_to_dict(self) -> None:
        meta = UnifiedMetadata(
            filename="rapport.xlsx",
            file_path="/data/rapport.xlsx",
            document_type=DocumentType.EXCEL,
            original_format=".xlsx",
            sheet_names=["Feuille1", "Feuille2"],
            has_tables=True,
            has_formulas=True,
        )

        d = meta.to_dict()

        assert d["document_type"] == "excel"
        assert d["sheet_names"] == ["Feuille1", "Feuille2"]
        assert d["has_tables"] is True
        assert d["has_formulas"] is True
        assert "indexed_at" in d

    def test_indexed_at_format(self) -> None:
        """indexed_at doit être au format ISO."""
        meta = UnifiedMetadata(
            filename="test.pdf",
            file_path="/test.pdf",
            document_type=DocumentType.PDF,
            original_format=".pdf",
        )

        d = meta.to_dict()

        # Vérifie que c'est un format ISO parsable
        datetime.fromisoformat(d["indexed_at"])


class TestUnifiedDocument:
    """Tests pour UnifiedDocument."""

    @pytest.fixture
    def sample_document(self) -> UnifiedDocument:
        """Fixture d'un document exemple."""
        return UnifiedDocument(
            metadata=UnifiedMetadata(
                document_id="test-doc-123",
                filename="rapport.xlsx",
                file_path="/data/rapport.xlsx",
                document_type=DocumentType.EXCEL,
                original_format=".xlsx",
                has_tables=True,
                has_formulas=True,
            ),
            content_markdown="# Rapport\n\nContenu du rapport...",
            structured_data=StructuredData(
                tables=[UnifiedTableData(headers=["A", "B"], rows=[[1, 2]])],
                formulas=[
                    FormulaData(
                        cell="B1",
                        sheet="Data",
                        formula="=A1*2",
                        result=2,
                    )
                ],
            ),
        )

    def test_properties(self, sample_document: UnifiedDocument) -> None:
        assert sample_document.document_id == "test-doc-123"
        assert sample_document.document_type == DocumentType.EXCEL
        assert sample_document.filename == "rapport.xlsx"

    def test_content_markdown(self, sample_document: UnifiedDocument) -> None:
        assert "# Rapport" in sample_document.content_markdown

    def test_structured_data_access(self, sample_document: UnifiedDocument) -> None:
        assert sample_document.structured_data.tables_count == 1
        assert sample_document.structured_data.formulas_count == 1

    def test_chunks_metadata_base(self, sample_document: UnifiedDocument) -> None:
        base = sample_document.get_chunks_metadata_base()

        assert base["document_id"] == "test-doc-123"
        assert base["doc_filename"] == "rapport.xlsx"
        assert base["document_type"] == "excel"
        assert base["has_table"] is True
        assert base["has_image"] is False
        assert base["has_formula"] is True

    def test_minimal_document(self) -> None:
        """Document minimal avec juste les champs requis."""
        doc = UnifiedDocument(
            metadata=UnifiedMetadata(
                filename="simple.pdf",
                file_path="/simple.pdf",
                document_type=DocumentType.PDF,
                original_format=".pdf",
            ),
            content_markdown="Simple content",
        )

        assert doc.document_id is not None
        assert doc.structured_data.tables_count == 0


class TestDocumentRouter:
    """Tests pour DocumentRouter."""

    def test_detect_type_pdf(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("file.pdf") == DocumentType.PDF
        assert router.detect_type("file.PDF") == DocumentType.PDF
        assert router.detect_type("/path/to/file.pdf") == DocumentType.PDF

    def test_detect_type_excel(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("file.xlsx") == DocumentType.EXCEL
        assert router.detect_type("file.xls") == DocumentType.EXCEL
        assert router.detect_type("file.XLSX") == DocumentType.EXCEL

    def test_detect_type_word(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("file.docx") == DocumentType.WORD
        assert router.detect_type("file.DOCX") == DocumentType.WORD

    def test_detect_type_unsupported(self) -> None:
        router = DocumentRouter()
        with pytest.raises(ValueError, match="Format non supporté"):
            router.detect_type("file.txt")

    def test_is_supported(self) -> None:
        router = DocumentRouter()
        assert router.is_supported("file.pdf") is True
        assert router.is_supported("file.xlsx") is True
        assert router.is_supported("file.xls") is True
        assert router.is_supported("file.docx") is True
        assert router.is_supported("file.txt") is False
        assert router.is_supported("file.csv") is False

    def test_get_supported_extensions(self) -> None:
        router = DocumentRouter()
        extensions = router.get_supported_extensions()

        assert ".pdf" in extensions
        assert ".xlsx" in extensions
        assert ".xls" in extensions
        assert ".docx" in extensions
        assert len(extensions) == 4


class TestChunkMetadataExtensions:
    """Tests pour les extensions ChunkMetadata multi-format."""

    def test_document_type_default(self) -> None:
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
        )

        assert meta.document_type == "pdf"

    def test_excel_fields(self) -> None:
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="excel",
            sheet_name="Feuille1",
            has_formula=True,
            formulas=[{"cell": "A1", "formula": "=SUM(B:B)"}],
        )

        assert meta.document_type == "excel"
        assert meta.sheet_name == "Feuille1"
        assert meta.has_formula is True
        assert meta.formulas is not None
        assert len(meta.formulas) == 1

    def test_word_fields(self) -> None:
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="word",
            heading_level=2,
        )

        assert meta.document_type == "word"
        assert meta.heading_level == 2

    def test_to_dict_includes_new_fields(self) -> None:
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="excel",
            sheet_name="Data",
            has_formula=True,
            heading_level=None,
        )

        d = meta.to_dict()

        assert d["document_type"] == "excel"
        assert d["sheet_name"] == "Data"
        assert d["has_formula"] is True
        assert d["heading_level"] is None

    def test_to_qdrant_payload_includes_new_fields(self) -> None:
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="excel",
            sheet_name="Sheet1",
            has_formula=True,
            formulas=[{"cell": "A1", "formula": "=1+1"}],
        )

        payload = meta.to_qdrant_payload()

        assert payload["document_type"] == "excel"
        assert payload["has_formula"] is True
        assert payload["sheet_name"] == "Sheet1"
        assert payload["formulas"] == [{"cell": "A1", "formula": "=1+1"}]

    def test_to_qdrant_payload_omits_none_optionals(self) -> None:
        """Les champs optionnels None ne sont pas inclus dans Qdrant."""
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_type="pdf",
        )

        payload = meta.to_qdrant_payload()

        assert "sheet_name" not in payload
        assert "formulas" not in payload
        assert "heading_level" not in payload
