# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour src/services/vector/filters.py (build_filter)."""

from __future__ import annotations

from qdrant_client.models import Filter, MatchText, MatchValue, Range

from src.services.vector.filters import build_filter


def test_returns_none_for_empty_filters() -> None:
    """build_filter({}) retourne None (aucune condition)."""
    assert build_filter({}) is None


def test_match_only_document_id() -> None:
    """document_id genere une condition MatchValue."""
    result = build_filter({"document_id": "doc-123"})

    assert isinstance(result, Filter)
    assert result.must is not None
    assert len(result.must) == 1
    cond = result.must[0]
    assert cond.key == "document_id"
    assert isinstance(cond.match, MatchValue)
    assert cond.match.value == "doc-123"


def test_match_multiple_keyword_fields() -> None:
    """Plusieurs filtres keyword sont accumules dans must."""
    result = build_filter(
        {
            "document_id": "doc-1",
            "content_type": "table",
            "section_title": "Intro",
            "doc_filename": "rapport.pdf",
        }
    )

    assert isinstance(result, Filter)
    assert result.must is not None
    keys = sorted(cond.key for cond in result.must)
    assert keys == ["content_type", "doc_filename", "document_id", "section_title"]


def test_bool_filters_only_when_true() -> None:
    """has_table=False est ignore (filtre par presence True uniquement)."""
    result = build_filter({"has_table": True, "has_image": False, "has_equation": True})

    assert isinstance(result, Filter)
    assert result.must is not None
    keys = sorted(cond.key for cond in result.must)
    assert keys == ["has_equation", "has_table"]


def test_range_only() -> None:
    """page_range=(start, end) genere un Range sur start_page."""
    result = build_filter({"page_range": (5, 10)})

    assert isinstance(result, Filter)
    assert result.must is not None
    assert len(result.must) == 1
    cond = result.must[0]
    assert cond.key == "start_page"
    assert isinstance(cond.range, Range)
    assert cond.range.gte == 5
    assert cond.range.lte == 10


def test_text_search_only() -> None:
    """text_search genere une condition MatchText sur content."""
    result = build_filter({"text_search": "qdrant"})

    assert isinstance(result, Filter)
    assert result.must is not None
    assert len(result.must) == 1
    cond = result.must[0]
    assert cond.key == "content"
    assert isinstance(cond.match, MatchText)
    assert cond.match.text == "qdrant"


def test_mixed_match_range_bool_text() -> None:
    """Combinaison match + range + bool + text_search."""
    result = build_filter(
        {
            "document_id": "doc-1",
            "page_range": (1, 3),
            "has_table": True,
            "text_search": "FastAPI",
        }
    )

    assert isinstance(result, Filter)
    assert result.must is not None
    assert len(result.must) == 4
    keys = sorted(cond.key for cond in result.must)
    assert keys == ["content", "document_id", "has_table", "start_page"]


def test_unknown_filter_key_ignored() -> None:
    """Une cle inconnue ne genere aucune condition."""
    result = build_filter({"unknown_field": "value"})

    assert result is None
