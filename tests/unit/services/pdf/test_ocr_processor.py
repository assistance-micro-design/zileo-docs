# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour MistralOCRProcessor (sans appels API reels)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import OCRAPIError, OCRRateLimitError
from src.services.pdf.ocr_processor import MistralOCRProcessor


class TestExtractMarkdownTables:
    """Tests pour _extract_markdown_tables: parsing de tableaux Markdown."""

    def test_returns_empty_when_no_table(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        assert proc._extract_markdown_tables("juste du texte") == []

    def test_parses_simple_table(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        tables = proc._extract_markdown_tables(md)
        assert len(tables) == 1
        assert tables[0].headers == ["A", "B"]
        assert tables[0].rows == 2
        assert tables[0].cols == 2
        assert tables[0].data == [["1", "2"], ["3", "4"]]


class TestExtractEquations:
    """Tests pour _extract_equations: detection LaTeX inline et block."""

    def test_returns_empty_when_no_equation(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        assert proc._extract_equations("texte simple") == []

    def test_detects_block_equation(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        eqs = proc._extract_equations("avant\n$$E = mc^2$$\napres")
        assert len(eqs) == 1
        assert eqs[0].type == "block"
        assert eqs[0].latex == "E = mc^2"

    def test_detects_inline_equation(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        eqs = proc._extract_equations("la formule $a + b$ est simple")
        inline = [e for e in eqs if e.type == "inline"]
        assert len(inline) == 1
        assert inline[0].latex == "a + b"

    def test_block_takes_precedence_over_inline(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        eqs = proc._extract_equations("$$x^2$$ et $y$")
        types = sorted(e.type for e in eqs)
        assert types == ["block", "inline"]


class TestDetectCharts:
    """Tests pour _detect_charts: heuristique mots-cles."""

    def test_returns_empty_when_no_keyword(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        assert proc._detect_charts("paragraphe normal") == []

    def test_detects_bar_chart(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        charts = proc._detect_charts("Voici un bar chart")
        assert len(charts) == 1
        assert charts[0].chart_type == "bar"

    def test_detects_pie_chart(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        charts = proc._detect_charts("Pie chart de la distribution")
        assert any(c.chart_type == "pie" for c in charts)


class TestErrorAndEmptyResults:
    """Tests pour _create_error_result et _create_empty_result."""

    def test_error_result_has_error_marker_in_markdown(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        result = proc._create_error_result(page_num=3, error="API down")
        assert result.page_number == 3
        assert "API down" in result.markdown_content
        assert result.confidence_score == 0.0
        assert result.tables == []

    def test_empty_result_has_zero_confidence(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        result = proc._create_empty_result(page_num=2, processing_time=42)
        assert result.page_number == 2
        assert result.confidence_score == 0.0
        assert result.processing_time_ms == 42


class TestCallOcrApiErrors:
    """Tests pour _call_ocr_api: mapping des erreurs Mistral vers exceptions metier."""

    @pytest.mark.asyncio
    async def test_rate_limit_raises_ocr_rate_limit_error(self) -> None:
        """Une exception contenant 'rate' devient OCRRateLimitError."""
        proc = MistralOCRProcessor(api_key="test-key")
        proc.client = MagicMock()
        proc.client.ocr.process = MagicMock(side_effect=RuntimeError("rate limit exceeded"))

        with pytest.raises(OCRRateLimitError):
            await proc._call_ocr_api("base64stub")

    @pytest.mark.asyncio
    async def test_status_429_raises_ocr_rate_limit_error(self) -> None:
        """Une erreur contenant '429' devient OCRRateLimitError."""
        proc = MistralOCRProcessor(api_key="test-key")
        proc.client = MagicMock()
        proc.client.ocr.process = MagicMock(side_effect=RuntimeError("got status 429"))

        with pytest.raises(OCRRateLimitError):
            await proc._call_ocr_api("base64stub")

    @pytest.mark.asyncio
    async def test_other_error_raises_ocr_api_error(self) -> None:
        """Une exception non-rate-limit devient OCRAPIError."""
        proc = MistralOCRProcessor(api_key="test-key")
        proc.client = MagicMock()
        proc.client.ocr.process = MagicMock(side_effect=RuntimeError("server unavailable"))

        with pytest.raises(OCRAPIError):
            await proc._call_ocr_api("base64stub")


class TestPageToBase64:
    """Tests pour _page_to_base64: conversion page PDF -> image base64."""

    def test_uses_fitz_open_and_encodes_pixmap(self, tmp_path: Path) -> None:
        """_page_to_base64 ouvre le PDF avec fitz et encode le pixmap en base64."""
        proc = MistralOCRProcessor(api_key="test-key")

        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"\x89PNGstub"
        mock_page = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc = MagicMock()
        mock_doc.__getitem__.return_value = mock_page

        with patch("src.services.pdf.ocr_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix = MagicMock()

            result = proc._page_to_base64(tmp_path / "doc.pdf", 0)

        assert isinstance(result, str)
        assert result  # base64 non vide
        mock_doc.close.assert_called_once()


class TestProcessPages:
    """Tests pour process_pages: orchestration parallele avec semaphore."""

    @pytest.mark.asyncio
    async def test_process_pages_returns_results_keyed_by_page(self, tmp_path: Path) -> None:
        """process_pages() retourne {page_num: OCRResult} pour chaque page."""
        proc = MistralOCRProcessor(api_key="test-key")
        proc._max_concurrent = 2

        async def fake_single_page(_path: Path, page_num: int, _opts: dict) -> object:
            return proc._create_empty_result(page_num, processing_time=10)

        with patch.object(proc, "_process_single_page", AsyncMock(side_effect=fake_single_page)):
            results = await proc.process_pages(tmp_path / "doc.pdf", [0, 1, 2])

        assert set(results.keys()) == {0, 1, 2}
        assert all(r.processing_time_ms == 10 for r in results.values())

    @pytest.mark.asyncio
    async def test_process_pages_converts_exception_into_error_result(self, tmp_path: Path) -> None:
        """Une exception dans une page produit un OCRResult error."""
        proc = MistralOCRProcessor(api_key="test-key")

        with patch.object(
            proc,
            "_process_single_page",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            results = await proc.process_pages(tmp_path / "doc.pdf", [0])

        assert 0 in results
        assert results[0].confidence_score == 0.0
        assert "boom" in results[0].markdown_content


class TestProcessSinglePage:
    """Tests pour _process_single_page: pipeline complet d'une page."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_api_response_has_no_pages(self) -> None:
        """Reponse OCR sans pages -> _create_empty_result."""
        proc = MistralOCRProcessor(api_key="test-key")

        empty_resp = MagicMock()
        empty_resp.pages = []

        with (
            patch.object(proc, "_page_to_base64", return_value="b64"),
            patch.object(proc, "_call_ocr_api", AsyncMock(return_value=empty_resp)),
        ):
            result = await proc._process_single_page(Path("/tmp/x.pdf"), 0, {})

        assert result.confidence_score == 0.0
        assert result.markdown_content == ""

    @pytest.mark.asyncio
    async def test_returns_error_result_on_api_error(self) -> None:
        """Une exception dans _call_ocr_api -> _create_error_result."""
        proc = MistralOCRProcessor(api_key="test-key")

        with (
            patch.object(proc, "_page_to_base64", return_value="b64"),
            patch.object(proc, "_call_ocr_api", AsyncMock(side_effect=OCRAPIError(500, "down"))),
        ):
            result = await proc._process_single_page(Path("/tmp/x.pdf"), 2, {})

        assert result.page_number == 2
        assert result.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_parses_markdown_and_returns_full_result(self) -> None:
        """Reponse valide -> markdown + tables/images/equations extraits."""
        proc = MistralOCRProcessor(api_key="test-key")

        page_content = MagicMock()
        page_content.markdown = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        page_content.images = []
        response = MagicMock()
        response.pages = [page_content]

        with (
            patch.object(proc, "_page_to_base64", return_value="b64"),
            patch.object(proc, "_call_ocr_api", AsyncMock(return_value=response)),
        ):
            result = await proc._process_single_page(Path("/tmp/x.pdf"), 1, {})

        assert result.page_number == 1
        assert result.markdown_content == page_content.markdown
        assert len(result.tables) == 1


class TestExtractHtmlTablesAndImages:
    """Tests pour _extract_html_tables et _extract_images."""

    def test_extract_html_tables_detects_table_tags(self) -> None:
        """_extract_html_tables() retourne 1 TableData par balise <table>."""
        proc = MistralOCRProcessor(api_key="test-key")
        markdown = "<p>intro</p><table><tr><td>a</td></tr></table>"

        tables = proc._extract_html_tables(markdown)

        assert len(tables) == 1
        assert tables[0].html.startswith("<table")

    def test_extract_images_includes_base64_when_requested(self) -> None:
        """_extract_images(include_base64=True) renvoie le champ base64."""
        proc = MistralOCRProcessor(api_key="test-key")
        img = MagicMock()
        img.description = "alt"
        img.bbox = None
        img.base64 = "stub"
        page_content = MagicMock()
        page_content.images = [img]

        result = proc._extract_images(page_content, include_base64=True)

        assert len(result) == 1
        assert result[0].base64 == "stub"


class TestMdTableToHtml:
    """Tests pour _md_table_to_html: conversion Markdown -> HTML."""

    def test_renders_thead_and_tbody(self) -> None:
        proc = MistralOCRProcessor(api_key="test-key")
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        html = proc._md_table_to_html(md)
        assert "<thead>" in html
        assert "<th>A</th>" in html
        assert "<th>B</th>" in html
        assert "<tbody>" in html
        assert "<td>1</td>" in html
        assert "<td>2</td>" in html
