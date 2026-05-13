# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Parsing structurel: fusion du contenu, regions protegees, sections."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from src.services.chunking.page_mapping import to_display_page


if TYPE_CHECKING:
    from src.models.extraction import ExtractedContent, OCRResult


# Patterns regex pour detection des regions et sections
_TABLE_PATTERN = re.compile(r"\|.+\|\n\|[-:| ]+\|\n(?:\|.+\|\n?)+")
_CODE_PATTERN = re.compile(r"```[\s\S]*?```")
_EQUATION_BLOCK_PATTERN = re.compile(r"\$\$[\s\S]*?\$\$")
_HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class _MarkdownSource(Protocol):
    """Protocole minimal pour accepter ExtractedContent ou OCRResult."""

    markdown_content: str | None


def merge_content(
    native: dict[int, ExtractedContent] | dict[int, _MarkdownSource],
    ocr: dict[int, OCRResult] | dict[int, _MarkdownSource],
    total_pages: int,
) -> tuple[str, dict[int, tuple[int, int, int]]]:
    """Fusionne les contenus natif et OCR dans l'ordre des pages.

    Priorite: contenu OCR > contenu natif.

    Returns:
        Tuple (contenu fusionne, mapping page_num -> (start_pos, end_pos, page_num)).
    """
    parts: list[str] = []
    page_mapping: dict[int, tuple[int, int, int]] = {}
    current_pos = 0

    for page_num in range(total_pages):
        page_marker = f"\n<!-- Page {to_display_page(page_num)} -->\n"
        parts.append(page_marker)
        current_pos += len(page_marker)

        content = ""
        if page_num in ocr and ocr[page_num].markdown_content:
            content = ocr[page_num].markdown_content or ""
        elif page_num in native and native[page_num].markdown_content:
            content = native[page_num].markdown_content or ""

        if content:
            start_pos = current_pos
            parts.append(content)
            parts.append("\n\n")
            current_pos += len(content) + 2
            end_pos = current_pos

            page_mapping[page_num] = (start_pos, end_pos, page_num)

    return "".join(parts), page_mapping


def identify_protected_regions(
    content: str,
    preserve_tables: bool = True,
    preserve_code: bool = True,
) -> list[tuple[int, int, str]]:
    """Identifie les regions a ne pas couper (tableaux, code, equations).

    Returns:
        Liste de tuples (start, end, type) triee par position de debut.
    """
    regions: list[tuple[int, int, str]] = []

    if preserve_tables:
        for match in _TABLE_PATTERN.finditer(content):
            regions.append((match.start(), match.end(), "table"))

    if preserve_code:
        for match in _CODE_PATTERN.finditer(content):
            regions.append((match.start(), match.end(), "code"))

    for match in _EQUATION_BLOCK_PATTERN.finditer(content):
        regions.append((match.start(), match.end(), "equation"))

    return sorted(regions, key=lambda x: x[0])


def parse_sections(content: str) -> list[dict[str, object]]:
    """Parse la hierarchie des sections depuis les headers Markdown.

    Returns:
        Liste de dictionnaires {level, title, hierarchy, position}.
    """
    sections: list[dict[str, object]] = []
    current_hierarchy: list[str] = []

    for match in _HEADER_PATTERN.finditer(content):
        level = len(match.group(1))
        title = match.group(2).strip()

        while len(current_hierarchy) >= level:
            current_hierarchy.pop()
        current_hierarchy.append(title)

        sections.append(
            {
                "level": level,
                "title": title,
                "hierarchy": current_hierarchy.copy(),
                "position": match.start(),
            }
        )

    return sections
