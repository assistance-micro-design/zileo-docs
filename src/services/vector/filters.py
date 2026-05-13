# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Construction des filtres Qdrant a partir d'un dictionnaire.

Extrait de QdrantVectorStore pour reduire le LOC du store principal
et permettre des tests unitaires dedies (filtres pures, sans I/O).
"""

from __future__ import annotations

from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue, Range


# Tables de mapping (approche table-driven)
_MATCH_FILTER_KEYS: tuple[str, ...] = (
    "document_id",
    "content_type",
    "section_title",
    "doc_filename",
)
_BOOL_FILTER_KEYS: tuple[str, ...] = ("has_table", "has_image", "has_equation")


def build_filter(filters: dict[str, Any]) -> Filter | None:
    """Construit un filtre Qdrant a partir d'un dictionnaire.

    Args:
        filters: Dictionnaire des filtres supportes:
            - document_id, content_type, section_title, doc_filename: MatchValue
            - has_table, has_image, has_equation: MatchValue(True) si vrai
            - page_range: tuple (start, end) -> Range sur start_page
            - text_search: MatchText sur content

    Returns:
        Filtre Qdrant ou None si aucune condition n'a ete generee.
    """
    conditions: list[FieldCondition] = []
    conditions.extend(_match_conditions(filters))
    conditions.extend(_bool_conditions(filters))

    range_cond = _range_condition(filters)
    if range_cond:
        conditions.append(range_cond)

    text_cond = _text_search_condition(filters)
    if text_cond:
        conditions.append(text_cond)

    return Filter(must=conditions) if conditions else None


def _match_conditions(filters: dict[str, Any]) -> list[FieldCondition]:
    """Conditions MatchValue pour les filtres keyword."""
    return [
        FieldCondition(key=key, match=MatchValue(value=filters[key]))
        for key in _MATCH_FILTER_KEYS
        if key in filters
    ]


def _bool_conditions(filters: dict[str, Any]) -> list[FieldCondition]:
    """Conditions booleennes (filtre uniquement si True)."""
    return [
        FieldCondition(key=key, match=MatchValue(value=True))
        for key in _BOOL_FILTER_KEYS
        if filters.get(key)
    ]


def _range_condition(filters: dict[str, Any]) -> FieldCondition | None:
    """Condition Range sur start_page a partir de page_range=(start, end)."""
    if "page_range" not in filters:
        return None
    start, end = filters["page_range"]
    return FieldCondition(key="start_page", range=Range(gte=start, lte=end))


def _text_search_condition(filters: dict[str, Any]) -> FieldCondition | None:
    """Condition MatchText sur content a partir de text_search."""
    if "text_search" not in filters:
        return None
    return FieldCondition(key="content", match=MatchText(text=filters["text_search"]))
