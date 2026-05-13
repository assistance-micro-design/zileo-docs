# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Helpers de mapping position -> pages (1-indexed pour affichage)."""

from __future__ import annotations


_PAGE_INDEX_OFFSET = 1


def to_display_page(page_num: int) -> int:
    """Convertit un numero de page 0-indexed (interne) en 1-indexed (affichage)."""
    return page_num + _PAGE_INDEX_OFFSET


def get_pages_at_position(
    pos: int,
    length: int,
    page_mapping: dict[int, tuple[int, int, int]] | None,
) -> set[int]:
    """Determine les pages (1-indexed) couvrant une plage de positions.

    Args:
        pos: Position de debut dans le contenu fusionne.
        length: Longueur du texte.
        page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

    Returns:
        Ensemble de numeros de pages (1-indexed).
    """
    if not page_mapping or pos == -1:
        return set()

    pages: set[int] = set()
    end_pos = pos + length
    for page_num, (page_start, page_end, _) in page_mapping.items():
        if pos < page_end and end_pos > page_start:
            pages.add(to_display_page(page_num))

    return pages


def get_pages_for_chunk(
    chunk: str,
    full_content: str,
    page_mapping: dict[int, tuple[int, int, int]],
) -> list[int]:
    """Fallback: determine les pages couvertes par un chunk via sa position.

    Utilise quand les pages n'ont pas ete propagees par le chunking.

    Args:
        chunk: Contenu du chunk.
        full_content: Contenu complet.
        page_mapping: Mapping page_num -> (start_pos, end_pos, page_num).

    Returns:
        Liste triee des numeros de pages (1-indexed); [1] si introuvable.
    """
    chunk_start = full_content.find(chunk)
    if chunk_start != -1:
        pages = get_pages_at_position(chunk_start, len(chunk), page_mapping)
        if pages:
            return sorted(pages)

    if len(chunk) > 50:
        chunk_start = full_content.find(chunk[:200])
        if chunk_start != -1:
            pages = get_pages_at_position(chunk_start, 200, page_mapping)
            if pages:
                return sorted(pages)

    return [1]
