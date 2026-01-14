"""Tests unitaires pour les models."""

from __future__ import annotations

from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.document import (
    DocumentAnalysisResult,
    DocumentMetadata,
    PageAnalysis,
    PageType,
)
from src.models.extraction import (
    ExtractedContent,
    HeaderInfo,
    OCRResult,
    TableData,
)


class TestDocumentMetadata:
    """Tests pour DocumentMetadata."""

    def test_create_metadata_minimal(self):
        """Test creation avec champs obligatoires uniquement."""
        meta = DocumentMetadata(
            document_id="test-123",
            file_hash="abc123",
            filename="test.pdf",
            file_size_bytes=1024,
        )
        assert meta.document_id == "test-123"
        assert meta.file_hash == "abc123"
        assert meta.filename == "test.pdf"
        assert meta.file_size_bytes == 1024
        assert meta.total_pages == 0
        assert meta.title is None

    def test_create_metadata_full(self, sample_document_metadata):
        """Test creation avec tous les champs."""
        meta = DocumentMetadata(**sample_document_metadata)
        assert meta.document_id == "doc-test-123"
        assert meta.title == "Document de Test"
        assert meta.total_pages == 10

    def test_default_timestamps(self):
        """Test que ingested_at est defini par defaut."""
        meta = DocumentMetadata(
            document_id="test",
            file_hash="hash",
            filename="test.pdf",
            file_size_bytes=100,
        )
        assert meta.ingested_at is not None
        assert meta.processed_at is None

    def test_to_dict(self):
        """Test conversion en dictionnaire."""
        meta = DocumentMetadata(
            document_id="test-123",
            file_hash="abc123",
            filename="test.pdf",
            file_size_bytes=1024,
            title="Test Title",
        )
        data = meta.to_dict()
        assert data["document_id"] == "test-123"
        assert data["title"] == "Test Title"
        assert "ingested_at" in data


class TestPageType:
    """Tests pour l'enum PageType."""

    def test_page_type_values(self):
        """Test les valeurs de l'enum."""
        assert PageType.TEXT_ONLY.value == "text_only"
        assert PageType.HAS_TABLES.value == "has_tables"
        assert PageType.SCANNED.value == "scanned"
        assert PageType.MIXED.value == "mixed"

    def test_page_type_from_string(self):
        """Test creation depuis une string."""
        assert PageType("text_only") == PageType.TEXT_ONLY
        assert PageType("has_tables") == PageType.HAS_TABLES


class TestPageAnalysis:
    """Tests pour PageAnalysis."""

    def test_create_page_analysis(self):
        """Test creation d'une analyse de page."""
        analysis = PageAnalysis(
            page_number=1,
            page_type=PageType.TEXT_ONLY,
            has_native_text=True,
            native_text_length=5000,
            has_images=False,
            image_count=0,
            image_coverage_ratio=0.0,
            has_tables=False,
            table_count=0,
            has_charts=False,
            width=612.0,
            height=792.0,
            rotation=0,
            extraction_method="pymupdf",
            priority=1,
        )
        assert analysis.page_number == 1
        assert analysis.page_type == PageType.TEXT_ONLY
        assert analysis.has_native_text is True

    def test_page_analysis_to_dict(self):
        """Test conversion en dictionnaire."""
        analysis = PageAnalysis(
            page_number=1,
            page_type=PageType.MIXED,
            has_native_text=True,
            native_text_length=1000,
            has_images=True,
            image_count=3,
            image_coverage_ratio=0.25,
            has_tables=True,
            table_count=1,
            has_charts=False,
            width=612.0,
            height=792.0,
            rotation=0,
            extraction_method="mistral_ocr",
            priority=2,
        )
        data = analysis.to_dict()
        assert data["page_type"] == "mixed"
        assert data["image_count"] == 3


class TestDocumentAnalysisResult:
    """Tests pour DocumentAnalysisResult."""

    def test_create_analysis_result(self):
        """Test creation d'un resultat d'analyse."""
        meta = DocumentMetadata(
            document_id="doc-1",
            file_hash="hash",
            filename="doc.pdf",
            file_size_bytes=1000,
        )
        result = DocumentAnalysisResult(
            metadata=meta,
            pages=[],
            pages_for_local_extraction=[1, 2, 3],
            pages_for_ocr=[4, 5],
        )
        assert result.metadata.document_id == "doc-1"
        assert result.pages_for_local_extraction == [1, 2, 3]
        assert result.pages_for_ocr == [4, 5]


class TestChunkMetadata:
    """Tests pour ChunkMetadata."""

    def test_create_chunk_metadata_minimal(self):
        """Test creation avec champs minimaux."""
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
        )
        assert meta.chunk_id == "chunk-1"
        assert meta.content_type == "text"
        assert meta.has_table is False
        assert meta.token_count == 0

    def test_create_chunk_metadata_full(self, sample_chunk_metadata):
        """Test creation avec tous les champs."""
        meta = ChunkMetadata(**sample_chunk_metadata)
        assert meta.chunk_id == "chunk-001"
        assert meta.page_numbers == [1, 2]
        assert meta.section_title == "Introduction"

    def test_section_hierarchy(self):
        """Test la hierarchie de sections."""
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            section_hierarchy=["Chapter 1", "Section 1.1", "Subsection 1.1.1"],
        )
        assert len(meta.section_hierarchy) == 3
        assert meta.section_hierarchy[0] == "Chapter 1"

    def test_to_qdrant_payload(self):
        """Test conversion en payload Qdrant."""
        meta = ChunkMetadata(
            chunk_id="chunk-1",
            document_id="doc-1",
            section_title=None,
            parent_chunk_id=None,
        )
        payload = meta.to_qdrant_payload()
        # Les None doivent etre convertis en string vide
        assert payload["section_title"] == ""
        assert payload["parent_chunk_id"] == ""


class TestDocumentChunk:
    """Tests pour DocumentChunk."""

    def test_create_chunk(self):
        """Test creation d'un chunk."""
        meta = ChunkMetadata(chunk_id="chunk-1", document_id="doc-1")
        chunk = DocumentChunk(
            content="Contenu du chunk de test.",
            metadata=meta,
        )
        assert chunk.content == "Contenu du chunk de test."
        assert chunk.metadata.chunk_id == "chunk-1"
        assert chunk.embedding is None
        assert chunk.has_embedding is False

    def test_chunk_with_embedding(self):
        """Test chunk avec embedding."""
        meta = ChunkMetadata(chunk_id="chunk-1", document_id="doc-1")
        chunk = DocumentChunk(
            content="Contenu",
            metadata=meta,
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        assert chunk.has_embedding is True
        assert len(chunk.embedding) == 4


class TestExtractedContent:
    """Tests pour ExtractedContent."""

    def test_create_extracted_content(self):
        """Test creation de contenu extrait."""
        content = ExtractedContent(
            page_number=1,
            markdown_content="# Titre\n\nParagraphe.",
        )
        assert content.page_number == 1
        assert content.extraction_method == "pymupdf4llm"
        assert len(content.headers) == 0

    def test_extracted_content_with_headers(self):
        """Test avec des headers."""
        headers = [
            HeaderInfo(level=1, text="Titre Principal", position=0),
            HeaderInfo(level=2, text="Sous-titre", position=50),
        ]
        content = ExtractedContent(
            page_number=1,
            markdown_content="# Titre\n\n## Sous-titre",
            headers=headers,
        )
        assert len(content.headers) == 2
        assert content.headers[0].level == 1


class TestOCRResult:
    """Tests pour OCRResult."""

    def test_create_ocr_result(self):
        """Test creation d'un resultat OCR."""
        result = OCRResult(
            page_number=1,
            markdown_content="Contenu OCR extrait.",
            confidence_score=0.95,
            processing_time_ms=1500,
        )
        assert result.page_number == 1
        assert result.confidence_score == 0.95
        assert len(result.tables) == 0

    def test_ocr_result_with_table(self):
        """Test avec un tableau extrait."""
        table = TableData(
            id="table-1",
            markdown="| A | B |\n|---|---|\n| 1 | 2 |",
            html="<table>...</table>",
            headers=["A", "B"],
            rows=2,
            cols=2,
            data=[["A", "B"], ["1", "2"]],
        )
        result = OCRResult(
            page_number=1,
            markdown_content="Texte avec tableau.",
            tables=[table],
        )
        assert len(result.tables) == 1
        assert result.tables[0].id == "table-1"
