# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests unitaires pour MistralOCRProcessor (sans appels API reels)."""

from __future__ import annotations

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
