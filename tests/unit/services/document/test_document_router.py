# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour DocumentRouter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.unified import DocumentType
from src.services.document.router import DocumentRouter


class TestDocumentRouterDetectType:
    """Tests pour detect_type."""

    def test_detect_pdf(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("document.pdf") == DocumentType.PDF

    def test_detect_xlsx(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("data.xlsx") == DocumentType.EXCEL

    def test_detect_xls(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("old_data.xls") == DocumentType.EXCEL

    def test_detect_docx(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("report.docx") == DocumentType.WORD

    def test_unsupported_format_raises(self) -> None:
        router = DocumentRouter()
        with pytest.raises(ValueError, match="Format non support"):
            router.detect_type("image.png")

    def test_case_insensitive(self) -> None:
        router = DocumentRouter()
        assert router.detect_type("REPORT.PDF") == DocumentType.PDF


class TestDocumentRouterIsSupported:
    """Tests pour is_supported."""

    def test_supported_pdf(self) -> None:
        router = DocumentRouter()
        assert router.is_supported("file.pdf") is True

    def test_unsupported_txt(self) -> None:
        router = DocumentRouter()
        assert router.is_supported("file.txt") is False


class TestDocumentRouterFileHash:
    """Tests pour le calcul du file_hash dans extract."""

    @pytest.mark.asyncio
    async def test_extract_excel_sets_file_hash(self) -> None:
        """L'extraction Excel doit calculer le SHA-256 du fichier."""
        from src.models.unified import DocumentType

        mock_excel_doc = MagicMock()
        mock_excel_doc.filename = "data.xlsx"
        mock_excel_doc.file_path = "/data/docs/data.xlsx"
        mock_excel_doc.format = "xlsx"
        mock_excel_doc.sheets = []
        mock_excel_doc.get_all_formulas.return_value = []
        mock_excel_doc.properties = {}
        mock_excel_doc.to_markdown.return_value = "content"

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=mock_excel_doc)

        router = DocumentRouter()
        router._initialized = True
        router._extractors[DocumentType.EXCEL] = mock_extractor

        with patch(
            "src.services.document.router.compute_file_hash",
            return_value="abc123",
        ):
            mock_path = MagicMock(spec=Path)
            mock_path.name = "data.xlsx"
            result = await router._extract_excel(mock_path)

        assert result.metadata.file_hash == "abc123"

    @pytest.mark.asyncio
    async def test_extract_word_sets_file_hash(self) -> None:
        """L'extraction Word doit calculer le SHA-256 du fichier."""
        from src.models.unified import DocumentType

        mock_word_doc = MagicMock()
        mock_word_doc.filename = "doc.docx"
        mock_word_doc.file_path = "/data/docs/doc.docx"
        mock_word_doc.tables = []
        mock_word_doc.images = []
        mock_word_doc.word_count = 100
        mock_word_doc.metadata = {}
        mock_word_doc.to_markdown.return_value = "content"

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=mock_word_doc)

        router = DocumentRouter()
        router._initialized = True
        router._extractors[DocumentType.WORD] = mock_extractor

        with patch(
            "src.services.document.router.compute_file_hash",
            return_value="def456",
        ):
            mock_path = MagicMock(spec=Path)
            mock_path.name = "doc.docx"
            result = await router._extract_word(mock_path)

        assert result.metadata.file_hash == "def456"


class TestDocumentRouterExtensions:
    """Tests pour get_supported_extensions."""

    def test_returns_all_extensions(self) -> None:
        router = DocumentRouter()
        exts = router.get_supported_extensions()

        assert ".pdf" in exts
        assert ".xlsx" in exts
        assert ".xls" in exts
        assert ".docx" in exts
        assert len(exts) == 4


class TestDocumentRouterInitialize:
    """Tests pour initialize()."""

    @pytest.mark.asyncio
    async def test_initialize_creates_excel_and_word_extractors(self) -> None:
        """initialize() instancie ExcelExtractor et WordExtractor."""
        router = DocumentRouter()

        await router.initialize()

        assert router._initialized is True
        assert DocumentType.EXCEL in router._extractors
        assert DocumentType.WORD in router._extractors

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self) -> None:
        """Un deuxieme appel a initialize() ne reinstancie pas les extracteurs."""
        router = DocumentRouter()

        await router.initialize()
        first_excel = router._extractors[DocumentType.EXCEL]

        await router.initialize()

        assert router._extractors[DocumentType.EXCEL] is first_excel


class TestDocumentRouterExtractDispatch:
    """Tests pour extract() (FileNotFoundError + dispatch par type)."""

    @pytest.mark.asyncio
    async def test_extract_raises_file_not_found(self, tmp_path: Path) -> None:
        """extract() leve FileNotFoundError sur un chemin inexistant."""
        router = DocumentRouter()
        missing = tmp_path / "missing.pdf"

        with pytest.raises(FileNotFoundError):
            await router.extract(missing)

    @pytest.mark.asyncio
    async def test_extract_routes_pdf_to_extract_pdf(self, tmp_path: Path) -> None:
        """extract() delegue les PDFs a _extract_pdf."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 stub")

        router = DocumentRouter()
        sentinel = MagicMock()

        with patch.object(router, "_extract_pdf", AsyncMock(return_value=sentinel)) as mock_pdf:
            result = await router.extract(pdf)

        mock_pdf.assert_awaited_once()
        assert result is sentinel

    @pytest.mark.asyncio
    async def test_extract_routes_xlsx_to_extract_excel(self, tmp_path: Path) -> None:
        """extract() delegue les Excel a _extract_excel."""
        xlsx = tmp_path / "data.xlsx"
        xlsx.write_bytes(b"PK\x03\x04 stub")

        router = DocumentRouter()
        sentinel = MagicMock()

        with patch.object(router, "_extract_excel", AsyncMock(return_value=sentinel)) as mock_excel:
            result = await router.extract(xlsx)

        mock_excel.assert_awaited_once()
        assert result is sentinel

    @pytest.mark.asyncio
    async def test_extract_routes_docx_to_extract_word(self, tmp_path: Path) -> None:
        """extract() delegue les Word a _extract_word."""
        docx = tmp_path / "report.docx"
        docx.write_bytes(b"PK\x03\x04 stub")

        router = DocumentRouter()
        sentinel = MagicMock()

        with patch.object(router, "_extract_word", AsyncMock(return_value=sentinel)) as mock_word:
            result = await router.extract(docx)

        mock_word.assert_awaited_once()
        assert result is sentinel


class TestDocumentRouterExtractPDF:
    """Tests pour _extract_pdf (mock DocumentPipelineOrchestrator import local)."""

    @pytest.mark.asyncio
    async def test_extract_pdf_returns_unified_document(self) -> None:
        """_extract_pdf() retourne un UnifiedDocument avec metadata renseignees."""
        mock_result = MagicMock()
        mock_result.total_pages = 7
        mock_result.has_tables = True
        mock_result.has_images = False
        mock_result.ocr_applied = True
        mock_result.get_all_content_markdown.return_value = "markdown body"

        mock_orchestrator = MagicMock()
        mock_orchestrator.initialize = AsyncMock()
        mock_orchestrator.process_document = AsyncMock(return_value=mock_result)

        router = DocumentRouter()
        path = MagicMock(spec=Path)
        path.name = "doc.pdf"
        path.absolute.return_value = Path("/data/docs/doc.pdf")

        with patch(
            "src.services.pipeline.orchestrator.DocumentPipelineOrchestrator",
            return_value=mock_orchestrator,
        ):
            result = await router._extract_pdf(path)

        assert result.metadata.document_type == DocumentType.PDF
        assert result.metadata.page_count == 7
        assert result.metadata.has_tables is True
        assert result.metadata.has_ocr_content is True
        assert result.content_markdown == "markdown body"

    @pytest.mark.asyncio
    async def test_extract_pdf_falls_back_to_content_attr(self) -> None:
        """_extract_pdf() utilise result.content quand get_all_content_markdown manque."""
        mock_result = MagicMock(spec=["content"])
        mock_result.content = "raw content"

        mock_orchestrator = MagicMock()
        mock_orchestrator.initialize = AsyncMock()
        mock_orchestrator.process_document = AsyncMock(return_value=mock_result)

        router = DocumentRouter()
        path = MagicMock(spec=Path)
        path.name = "doc.pdf"
        path.absolute.return_value = Path("/data/docs/doc.pdf")

        with patch(
            "src.services.pipeline.orchestrator.DocumentPipelineOrchestrator",
            return_value=mock_orchestrator,
        ):
            result = await router._extract_pdf(path)

        assert result.content_markdown == "raw content"
        assert result.metadata.has_ocr_content is False


class TestDocumentRouterWordTablesEdgeCase:
    """Tests pour les branches edge de _word_tables (extraction headers depuis rows[0])."""

    @pytest.mark.asyncio
    async def test_word_tables_extracts_headers_from_first_row_when_missing(self) -> None:
        """_word_tables() construit les headers depuis la 1re ligne si absents."""
        from src.models.unified import DocumentType

        cell = MagicMock()
        cell.text = "Header1"
        cell2 = MagicMock()
        cell2.text = "Header2"
        cell3 = MagicMock()
        cell3.text = "data1"
        cell4 = MagicMock()
        cell4.text = "data2"

        table = MagicMock()
        table.headers = []
        table.rows = [[cell, cell2], [cell3, cell4]]

        word_doc = MagicMock()
        word_doc.filename = "doc.docx"
        word_doc.file_path = "/data/docs/doc.docx"
        word_doc.tables = [table]
        word_doc.images = []
        word_doc.word_count = 10
        word_doc.metadata = {}
        word_doc.to_markdown.return_value = "content"

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=word_doc)

        router = DocumentRouter()
        router._initialized = True
        router._extractors[DocumentType.WORD] = mock_extractor

        with patch(
            "src.services.document.router.compute_file_hash",
            return_value="hash",
        ):
            path = MagicMock(spec=Path)
            path.name = "doc.docx"
            result = await router._extract_word(path)

        assert result.metadata.has_tables is True
