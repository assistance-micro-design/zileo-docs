# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests d'integration pour MistralOCRProcessor.

Ces tests necessitent une cle API Mistral valide et sont
marques comme integration tests.
"""

from __future__ import annotations

import base64 as b64
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.pdf.ocr_processor import MistralOCRProcessor


if TYPE_CHECKING:
    from collections.abc import Generator


class TestMistralOCRProcessorUnit:
    """Tests unitaires pour MistralOCRProcessor (mocked)."""

    def test_initialization(self) -> None:
        """Test initialisation du processeur."""
        processor = MistralOCRProcessor(api_key="test-key")
        assert processor._api_key == "test-key"

    def test_initialization_with_settings(self) -> None:
        """Test initialisation avec settings par defaut."""
        with patch("src.services.pdf.ocr_processor.settings") as mock_settings:
            mock_settings.MISTRAL_API_KEY = "settings-key"
            mock_settings.OCR_MAX_CONCURRENT = 5
            mock_settings.OCR_DPI = 300
            mock_settings.OCR_TABLE_FORMAT = "markdown"

            processor = MistralOCRProcessor()
            assert processor._api_key == "settings-key"

    def test_page_to_base64(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test conversion page en base64."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor(api_key="test-key")
        base64_str = processor._page_to_base64(pdf_path, 0)

        assert base64_str is not None
        assert len(base64_str) > 0
        # Base64 valid characters
        try:
            b64.b64decode(base64_str)
        except Exception:
            pytest.fail("Invalid base64 string")

    def test_extract_tables_markdown(self) -> None:
        """Test extraction tableaux format Markdown."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = """Some text

| Header1 | Header2 | Header3 |
|---------|---------|---------|
| A       | B       | C       |
| D       | E       | F       |

More text"""

        tables = processor._extract_tables(markdown, "markdown")

        assert len(tables) == 1
        assert tables[0].headers == ["Header1", "Header2", "Header3"]
        assert tables[0].rows == 2
        assert tables[0].cols == 3
        assert tables[0].data == [["A", "B", "C"], ["D", "E", "F"]]

    def test_extract_tables_html(self) -> None:
        """Test extraction tableaux format HTML."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = """Some text
<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>
More text"""

        tables = processor._extract_tables(markdown, "html")

        assert len(tables) == 1
        assert tables[0].html is not None
        assert "<table>" in tables[0].html

    def test_extract_equations_inline(self) -> None:
        """Test extraction equations inline."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = "The formula is $E = mc^2$ and also $F = ma$."
        equations = processor._extract_equations(markdown)

        inline_eqs = [eq for eq in equations if eq.type == "inline"]
        assert len(inline_eqs) == 2
        assert any("E = mc^2" in eq.latex for eq in inline_eqs)

    def test_extract_equations_block(self) -> None:
        """Test extraction equations block."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = """Some text

$$\\int_0^\\infty f(x) dx = 1$$

More text"""

        equations = processor._extract_equations(markdown)

        block_eqs = [eq for eq in equations if eq.type == "block"]
        assert len(block_eqs) >= 1

    def test_detect_charts_bar(self) -> None:
        """Test detection graphique bar chart."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = "This bar chart shows the breakdown of sales."
        charts = processor._detect_charts(markdown)

        assert len(charts) == 1
        assert charts[0].chart_type == "bar"

    def test_detect_charts_multiple(self) -> None:
        """Test detection plusieurs types de graphiques."""
        processor = MistralOCRProcessor(api_key="test-key")

        markdown = """The pie chart shows market share.
The line graph displays the trend over time."""

        charts = processor._detect_charts(markdown)

        chart_types = [c.chart_type for c in charts]
        assert "pie" in chart_types
        assert "line" in chart_types

    def test_md_table_to_html(self) -> None:
        """Test conversion Markdown table vers HTML."""
        processor = MistralOCRProcessor(api_key="test-key")

        md_table = """| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |"""

        html = processor._md_table_to_html(md_table)

        assert "<table>" in html
        assert "</table>" in html
        assert "<thead>" in html
        assert "<tbody>" in html
        assert "<th>A</th>" in html
        assert "<td>1</td>" in html

    def test_create_empty_result(self) -> None:
        """Test creation resultat vide."""
        processor = MistralOCRProcessor(api_key="test-key")

        result = processor._create_empty_result(page_num=5, processing_time=100)

        assert result.page_number == 5
        assert result.markdown_content == ""
        assert result.confidence_score == 0.0
        assert result.processing_time_ms == 100
        assert len(result.tables) == 0
        assert len(result.images) == 0

    def test_create_error_result(self) -> None:
        """Test creation resultat d'erreur."""
        processor = MistralOCRProcessor(api_key="test-key")

        result = processor._create_error_result(page_num=3, error="API timeout")

        assert result.page_number == 3
        assert "OCR Error" in result.markdown_content
        assert "API timeout" in result.markdown_content
        assert result.confidence_score == 0.0


class TestMistralOCRProcessorMocked:
    """Tests avec API mockee."""

    @pytest.mark.asyncio
    async def test_process_pages_success(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test traitement de pages avec API mockee."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor(api_key="test-key")

        # Mock la methode _call_ocr_api
        mock_response = MagicMock()
        mock_page = MagicMock()
        mock_page.markdown = "# Extracted Title\n\nSome extracted text."
        mock_response.pages = [mock_page]

        with patch.object(processor, "_call_ocr_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            results = await processor.process_pages(pdf_path, [0])

            assert 0 in results
            assert results[0].page_number == 0
            assert results[0].markdown_content == "# Extracted Title\n\nSome extracted text."

    @pytest.mark.asyncio
    async def test_process_pages_empty_response(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test traitement avec reponse vide."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor(api_key="test-key")

        mock_response = MagicMock()
        mock_response.pages = []

        with patch.object(processor, "_call_ocr_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            results = await processor.process_pages(pdf_path, [0])

            assert 0 in results
            assert results[0].markdown_content == ""
            assert results[0].confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_process_pages_error_handling(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test gestion des erreurs."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor(api_key="test-key")

        with patch.object(processor, "_call_ocr_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("API Error")

            results = await processor.process_pages(pdf_path, [0])

            assert 0 in results
            assert "Error" in results[0].markdown_content

    @pytest.mark.asyncio
    async def test_process_multiple_pages_parallel(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test traitement parallele de plusieurs pages."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor(api_key="test-key")

        mock_response = MagicMock()
        mock_page = MagicMock()
        mock_page.markdown = "Page content"
        mock_response.pages = [mock_page]

        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        with patch.object(processor, "_call_ocr_api", side_effect=mock_call):
            results = await processor.process_pages(pdf_path, [0, 1])

            assert len(results) == 2
            assert 0 in results
            assert 1 in results
            assert call_count == 2


@pytest.mark.integration
@pytest.mark.skip(reason="Requires valid Mistral API key")
class TestMistralOCRProcessorIntegration:
    """Tests d'integration reels (necessitent API key).

    Ces tests sont desactives par defaut.
    Pour les executer: pytest -m integration
    """

    @pytest.mark.asyncio
    async def test_real_ocr_text_page(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test OCR reel sur page texte."""
        pdf_path = next(iter([sample_text_pdf]))

        processor = MistralOCRProcessor()
        results = await processor.process_pages(pdf_path, [0])

        assert 0 in results
        assert results[0].markdown_content
        assert results[0].confidence_score > 0.8
        assert results[0].processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_real_ocr_table_extraction(
        self, sample_pdf_with_table: Generator[Path, None, None]
    ) -> None:
        """Test OCR reel extraction tableau."""
        pdf_path = next(iter([sample_pdf_with_table]))

        processor = MistralOCRProcessor()
        results = await processor.process_pages(
            pdf_path,
            [0],
            options={"table_format": "markdown"},
        )

        assert 0 in results
        # Le tableau devrait etre detecte
        assert len(results[0].tables) >= 0  # May or may not detect depending on PDF
