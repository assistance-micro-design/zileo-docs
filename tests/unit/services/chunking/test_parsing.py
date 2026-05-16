# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/services/chunking/parsing.py."""

from __future__ import annotations

from src.services.chunking.parsing import (
    identify_protected_regions,
    merge_content,
    parse_sections,
)


def test_parse_sections_extracts_headers() -> None:
    """parse_sections() retourne les headers avec niveau et hierarchie."""
    content = "# Title\n\n## Sub A\n\ncontent\n\n## Sub B"

    sections = parse_sections(content)

    titles = [s["title"] for s in sections]
    assert titles == ["Title", "Sub A", "Sub B"]
    levels = [s["level"] for s in sections]
    assert levels == [1, 2, 2]


def test_parse_sections_builds_hierarchy() -> None:
    """parse_sections() construit la hierarchie parent/enfant."""
    content = "# H1\n## H2\n### H3"

    sections = parse_sections(content)

    assert sections[0]["hierarchy"] == ["H1"]
    assert sections[1]["hierarchy"] == ["H1", "H2"]
    assert sections[2]["hierarchy"] == ["H1", "H2", "H3"]


def test_parse_sections_resets_on_new_top_level() -> None:
    """Un nouveau header top-level reset la hierarchie."""
    content = "# A\n## a1\n# B\n## b1"

    sections = parse_sections(content)

    assert sections[2]["title"] == "B"
    assert sections[2]["hierarchy"] == ["B"]
    assert sections[3]["hierarchy"] == ["B", "b1"]


def test_identify_protected_regions_table() -> None:
    """identify_protected_regions() detecte les tableaux."""
    content = "intro\n| h | h |\n| - | - |\n| a | b |\nend"

    regions = identify_protected_regions(content, preserve_tables=True, preserve_code=False)

    assert len(regions) == 1
    assert regions[0][2] == "table"


def test_identify_protected_regions_code() -> None:
    """identify_protected_regions() detecte les blocs de code."""
    content = "intro\n```python\nx = 1\n```\nend"

    regions = identify_protected_regions(content, preserve_tables=False, preserve_code=True)

    assert len(regions) == 1
    assert regions[0][2] == "code"


def test_identify_protected_regions_equation() -> None:
    """identify_protected_regions() detecte les equations en bloc."""
    content = "before\n$$E = mc^2$$\nafter"

    regions = identify_protected_regions(content, preserve_tables=False, preserve_code=False)

    assert len(regions) == 1
    assert regions[0][2] == "equation"


def test_identify_protected_regions_sorted_by_start() -> None:
    """Les regions sont triees par position de debut."""
    content = "```\ncode\n```\n\n$$eq$$\n\n| a | b |\n| - | - |\n| 1 | 2 |"

    regions = identify_protected_regions(content, preserve_tables=True, preserve_code=True)

    starts = [r[0] for r in regions]
    assert starts == sorted(starts)


def test_identify_protected_regions_respects_flags() -> None:
    """Les flags preserve_tables/preserve_code masquent les regions correspondantes."""
    content = "```\ncode\n```\n\n| h |\n| - |\n| a |"

    regions = identify_protected_regions(content, preserve_tables=False, preserve_code=False)

    types = [r[2] for r in regions]
    assert "table" not in types
    assert "code" not in types


def test_merge_content_orders_pages_with_markers() -> None:
    """merge_content() concatene les pages dans l'ordre avec marqueurs."""

    class _Stub:
        def __init__(self, markdown: str) -> None:
            self.markdown_content = markdown

    native = {0: _Stub("page-0 text"), 1: _Stub("page-1 text")}
    ocr: dict[int, _Stub] = {}

    merged, mapping = merge_content(native, ocr, total_pages=2)

    assert "<!-- Page 1 -->" in merged
    assert "<!-- Page 2 -->" in merged
    assert merged.index("page-0 text") < merged.index("page-1 text")
    assert 0 in mapping
    assert 1 in mapping


def test_merge_content_ocr_overrides_native() -> None:
    """Le contenu OCR a priorite sur le natif sur la meme page."""

    class _Stub:
        def __init__(self, markdown: str) -> None:
            self.markdown_content = markdown

    native = {0: _Stub("native version")}
    ocr = {0: _Stub("ocr version")}

    merged, _ = merge_content(native, ocr, total_pages=1)

    assert "ocr version" in merged
    assert "native version" not in merged
