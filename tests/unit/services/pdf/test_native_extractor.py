# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests unitaires pour NativeContentExtractor."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.services.pdf.native_extractor import NativeContentExtractor


if TYPE_CHECKING:
    from collections.abc import Generator


class TestNativeContentExtractor:
    """Tests pour NativeContentExtractor."""

    @pytest.mark.asyncio
    async def test_extract_single_page(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test extraction d'une seule page."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        assert 0 in results
        content = results[0]

        assert content.page_number == 0
        assert content.markdown_content is not None
        assert len(content.markdown_content) > 0
        assert content.extraction_method == "pymupdf4llm"
        assert content.char_count > 0
        assert content.word_count > 0

    @pytest.mark.asyncio
    async def test_extract_multiple_pages(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test extraction de plusieurs pages."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0, 1])

        assert len(results) == 2
        assert 0 in results
        assert 1 in results

        for page_num, content in results.items():
            assert content.page_number == page_num
            assert content.markdown_content is not None

    @pytest.mark.asyncio
    async def test_extract_empty_page(self, sample_empty_pdf: Generator[Path, None, None]) -> None:
        """Test extraction d'une page vide."""
        pdf_path = next(iter([sample_empty_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        assert 0 in results
        content = results[0]

        # Page vide = peu ou pas de contenu
        assert content.page_number == 0
        # Peut avoir du contenu minimal ou vide
        assert content.char_count >= 0

    @pytest.mark.asyncio
    async def test_headers_extraction(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test extraction des headers."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]

        # Les headers sont une liste
        assert isinstance(content.headers, list)

        # Si des headers sont detectes
        for header in content.headers:
            assert 1 <= header.level <= 6
            assert header.text is not None
            assert header.position >= 0

    @pytest.mark.asyncio
    async def test_paragraphs_extraction(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test extraction des paragraphes."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]

        assert isinstance(content.paragraphs, list)
        # Chaque paragraphe est une string non vide
        for para in content.paragraphs:
            assert isinstance(para, str)

    @pytest.mark.asyncio
    async def test_lists_extraction(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test extraction des listes."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]

        assert isinstance(content.lists, list)

        for lst in content.lists:
            assert lst.type in ("bullet", "numbered")
            assert isinstance(lst.items, list)

    @pytest.mark.asyncio
    async def test_table_placeholders(
        self, sample_pdf_with_table: Generator[Path, None, None]
    ) -> None:
        """Test detection des placeholders de tableaux."""
        pdf_path = next(iter([sample_pdf_with_table]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]

        # Les table_placeholders sont une liste
        assert isinstance(content.table_placeholders, list)

        for placeholder in content.table_placeholders:
            assert placeholder.id is not None
            assert placeholder.position >= 0
            assert placeholder.rows >= 0
            assert placeholder.cols >= 0

    @pytest.mark.asyncio
    async def test_image_placeholders(self, sample_text_pdf: Generator[Path, None, None]) -> None:
        """Test detection des placeholders d'images."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]

        # Les image_placeholders sont une liste
        assert isinstance(content.image_placeholders, list)

        for placeholder in content.image_placeholders:
            assert placeholder.id is not None
            assert placeholder.position >= 0

    @pytest.mark.asyncio
    async def test_to_dict_serialization(
        self, sample_text_pdf: Generator[Path, None, None]
    ) -> None:
        """Test serialisation en dictionnaire."""
        pdf_path = next(iter([sample_text_pdf]))

        extractor = NativeContentExtractor(pdf_path)
        results = await extractor.extract_pages([0])

        content = results[0]
        content_dict = content.to_dict()

        assert "page_number" in content_dict
        assert "markdown_content" in content_dict
        assert "extraction_method" in content_dict
        assert "headers" in content_dict
        assert "paragraphs" in content_dict
        assert "lists" in content_dict
        assert "char_count" in content_dict
        assert "word_count" in content_dict


class TestExtractorHelperMethods:
    """Tests pour les methodes helper de l'extracteur."""

    def test_extract_headers_pattern(self) -> None:
        """Test du pattern d'extraction des headers."""
        extractor = NativeContentExtractor("/tmp/test.pdf")

        md = "# Title 1\n\nSome text\n\n## Title 2\n\nMore text\n\n### Title 3"
        headers = extractor._extract_headers(md)

        assert len(headers) == 3
        assert headers[0].level == 1
        assert headers[0].text == "Title 1"
        assert headers[1].level == 2
        assert headers[1].text == "Title 2"
        assert headers[2].level == 3
        assert headers[2].text == "Title 3"

    def test_extract_lists_bullet(self) -> None:
        """Test extraction des listes a puces."""
        extractor = NativeContentExtractor("/tmp/test.pdf")

        md = "Some text\n\n- Item 1\n- Item 2\n- Item 3\n\nMore text"
        lists = extractor._extract_lists(md)

        bullet_lists = [lst for lst in lists if lst.type == "bullet"]
        assert len(bullet_lists) >= 1
        assert "Item 1" in bullet_lists[0].items

    def test_extract_lists_numbered(self) -> None:
        """Test extraction des listes numerotees."""
        extractor = NativeContentExtractor("/tmp/test.pdf")

        md = "Some text\n\n1. First\n2. Second\n3. Third\n\nMore text"
        lists = extractor._extract_lists(md)

        numbered_lists = [lst for lst in lists if lst.type == "numbered"]
        assert len(numbered_lists) >= 1
        assert "First" in numbered_lists[0].items

    def test_detect_tables_markdown(self) -> None:
        """Test detection des tableaux Markdown."""
        extractor = NativeContentExtractor("/tmp/test.pdf")

        md = """Some text

| Col1 | Col2 | Col3 |
|------|------|------|
| A    | B    | C    |
| D    | E    | F    |

More text"""

        tables = extractor._detect_tables(md)

        assert len(tables) == 1
        assert tables[0].rows == 3  # header + 2 data rows (separator excluded)
        assert tables[0].cols == 3

    def test_detect_images_markdown(self) -> None:
        """Test detection des images Markdown."""
        extractor = NativeContentExtractor("/tmp/test.pdf")

        md = "Some text\n\n![Alt text](image.png)\n\n![Another](pic.jpg)"
        images = extractor._detect_images(md)

        assert len(images) == 2
        assert images[0].alt_text == "Alt text"
        assert images[0].path == "image.png"
        assert images[1].alt_text == "Another"
        assert images[1].path == "pic.jpg"
