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
