# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour DocumentAnalyzer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.core.exceptions import SourceFileNotFoundError
from src.models.document import PageType
from src.services.pdf.analyzer import DocumentAnalyzer


if TYPE_CHECKING:
    from collections.abc import Generator


class TestDocumentAnalyzer:
    """Tests pour DocumentAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyze_text_only_pdf(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test analyse d'un PDF avec texte simple."""
        pdf_path = next(iter([sample_text_pdf]))  # Get the path from generator context

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        # Verifier metadonnees
        assert result.metadata.document_id is not None
        assert result.metadata.file_hash is not None
        assert result.metadata.filename == "text_only.pdf"
        assert result.metadata.total_pages == 2

        # Verifier analyse des pages
        assert len(result.pages) == 2
        assert all(p.page_type == PageType.TEXT_ONLY for p in result.pages)
        assert all(p.extraction_method == "pymupdf" for p in result.pages)

        # Verifier plan d'extraction
        assert len(result.pages_for_local_extraction) == 2
        assert len(result.pages_for_ocr) == 0

    @pytest.mark.asyncio
    async def test_analyze_empty_pdf(self, sample_empty_pdf: Generator[Path, None, None]) -> None:
        """Test analyse d'un PDF vide."""
        pdf_path = next(iter([sample_empty_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        assert result.metadata.total_pages == 1
        assert len(result.pages) == 1

        # Page vide -> peu de texte
        page = result.pages[0]
        assert page.native_text_length < 50
        assert not page.has_native_text

    @pytest.mark.asyncio
    async def test_analyze_multipage_pdf(
        self, sample_multipage_pdf: Generator[Path, None, None]
    ) -> None:
        """Test analyse d'un PDF multi-pages."""
        pdf_path = next(iter([sample_multipage_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        assert result.metadata.total_pages == 3
        assert len(result.pages) == 3

        # Toutes les pages doivent etre assignees
        all_pages = set(range(3))
        assigned_pages = set(result.pages_for_local_extraction + result.pages_for_ocr)
        assert all_pages == assigned_pages

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_file(self, tmp_path: Path) -> None:
        """Test avec fichier inexistant."""
        pdf_path = tmp_path / "nonexistent.pdf"

        analyzer = DocumentAnalyzer(pdf_path)

        with pytest.raises(SourceFileNotFoundError) as exc_info:
            await analyzer.analyze()

        assert "nonexistent.pdf" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test extraction des metadonnees."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        metadata = result.metadata
        assert metadata.document_id is not None
        assert len(metadata.file_hash) == 64  # SHA-256
        assert metadata.file_size_bytes > 0
        assert metadata.ingested_at is not None
        assert metadata.processed_at is None  # Pas encore traite

    @pytest.mark.asyncio
    async def test_page_analysis_attributes(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test attributs de l'analyse de page."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        page = result.pages[0]

        # Attributs requis
        assert page.page_number == 0
        assert page.page_type in PageType
        assert isinstance(page.has_native_text, bool)
        assert page.native_text_length >= 0
        assert page.width > 0
        assert page.height > 0
        assert page.rotation in (0, 90, 180, 270)
        assert page.extraction_method in ("pymupdf", "mistral_ocr")
        assert page.priority >= 1

    @pytest.mark.asyncio
    async def test_estimations_calculated(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test calcul des estimations."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        assert result.estimated_tokens >= 0
        assert result.estimated_ocr_cost >= 0.0
        assert result.estimated_processing_time_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_to_dict_serialization(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test serialisation en dictionnaire."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        result_dict = result.to_dict()

        assert "metadata" in result_dict
        assert "pages" in result_dict
        assert "pages_for_local_extraction" in result_dict
        assert "pages_for_ocr" in result_dict
        assert "estimated_tokens" in result_dict


class TestPageClassification:
    """Tests pour la classification des pages."""

    @pytest.mark.asyncio
    async def test_text_only_classification(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test classification TEXT_ONLY."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        # Pages avec beaucoup de texte = TEXT_ONLY
        for page in result.pages:
            if page.native_text_length > 50:
                assert page.page_type == PageType.TEXT_ONLY

    @pytest.mark.asyncio
    async def test_extraction_method_assignment(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test assignation methode d'extraction."""
        pdf_path = next(iter([sample_text_pdf]))

        analyzer = DocumentAnalyzer(pdf_path)
        result = await analyzer.analyze()

        for page in result.pages:
            if page.page_type == PageType.TEXT_ONLY:
                assert page.extraction_method == "pymupdf"
            else:
                assert page.extraction_method == "mistral_ocr"


class TestAnalyzerConfiguration:
    """Tests pour la configuration de l'analyseur."""

    def test_default_thresholds(self) -> None:
        """Test valeurs par defaut des seuils."""
        analyzer = DocumentAnalyzer("/tmp/test.pdf")

        assert analyzer.MIN_TEXT_FOR_NATIVE == 50
        assert analyzer.SIGNIFICANT_IMAGE_RATIO == 0.05
        assert analyzer.CHART_DRAWING_THRESHOLD == 50
        assert analyzer.CHART_TEXT_MAX_LENGTH == 500
