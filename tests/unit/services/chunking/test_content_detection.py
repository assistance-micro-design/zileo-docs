# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour src/services/chunking/content_detection.py."""

from __future__ import annotations

from src.services.chunking.content_detection import has_equation, has_image, has_table


def test_has_table_detects_markdown_table() -> None:
    """has_table() retourne True sur un tableau Markdown classique."""
    content = "| col1 | col2 |\n| --- | --- |\n| a | b |"

    assert has_table(content) is True


def test_has_table_returns_false_on_plain_text() -> None:
    """has_table() retourne False sur du texte simple."""
    assert has_table("Just a sentence with | pipes |") is False
    assert has_table("plain text") is False


def test_has_image_detects_markdown_image() -> None:
    """has_image() retourne True sur la syntaxe ![alt](url)."""
    assert has_image("![alt text](https://example.com/img.png)") is True


def test_has_image_returns_false_when_no_image() -> None:
    """has_image() retourne False quand pas de motif ![..]."""
    assert has_image("just text") is False
    assert has_image("[link](url) but no image") is False


def test_has_equation_detects_dollar_sign() -> None:
    """has_equation() retourne True sur la presence d'un $."""
    assert has_equation("inline math $x^2$ here") is True
    assert has_equation("$$\nE = mc^2\n$$") is True


def test_has_equation_returns_false_when_no_dollar() -> None:
    """has_equation() retourne False sans signe $."""
    assert has_equation("no math here") is False
