# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/services/chunking/page_mapping.py."""

from __future__ import annotations

from src.services.chunking.page_mapping import (
    get_pages_at_position,
    get_pages_for_chunk,
    to_display_page,
)


def test_to_display_page_zero_indexed_to_one_indexed() -> None:
    """to_display_page() ajoute l'offset 1 (0-indexed -> 1-indexed)."""
    assert to_display_page(0) == 1
    assert to_display_page(5) == 6


def test_get_pages_at_position_no_mapping_returns_empty() -> None:
    """page_mapping=None retourne un set vide."""
    assert get_pages_at_position(0, 100, None) == set()


def test_get_pages_at_position_negative_position_returns_empty() -> None:
    """pos=-1 (introuvable) retourne un set vide."""
    mapping = {0: (0, 100, 0)}

    assert get_pages_at_position(-1, 50, mapping) == set()


def test_get_pages_at_position_single_page() -> None:
    """Une position couvrant une seule page retourne {page+1}."""
    mapping = {0: (0, 100, 0), 1: (100, 200, 1)}

    pages = get_pages_at_position(10, 20, mapping)

    assert pages == {1}


def test_get_pages_at_position_spans_two_pages() -> None:
    """Une plage chevauchant deux pages retourne les deux."""
    mapping = {0: (0, 100, 0), 1: (100, 200, 1)}

    pages = get_pages_at_position(80, 50, mapping)

    assert pages == {1, 2}


def test_get_pages_for_chunk_finds_chunk_in_content() -> None:
    """get_pages_for_chunk() retrouve les pages quand le chunk existe dans le contenu."""
    full_content = "page 1 content. page 2 content."
    chunk = "page 2 content."
    mapping = {0: (0, 15, 0), 1: (16, len(full_content), 1)}

    pages = get_pages_for_chunk(chunk, full_content, mapping)

    assert 2 in pages


def test_get_pages_for_chunk_fallback_when_not_found() -> None:
    """get_pages_for_chunk() retourne [1] quand le chunk n'est pas trouvable."""
    pages = get_pages_for_chunk("not in content", "some other text", {})

    assert pages == [1]
