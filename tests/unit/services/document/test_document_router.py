"""Tests unitaires pour DocumentRouter."""

from __future__ import annotations

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
