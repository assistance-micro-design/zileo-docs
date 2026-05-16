# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Helpers d'extraction du payload Qdrant."""

from __future__ import annotations

from typing import Any


def extract_doc_summary(chunk: dict[str, Any]) -> dict[str, Any]:
    """Extrait les metadonnees du document depuis un chunk Qdrant.

    Centralise l'acces aux cles payload `doc_*` (cf. _build_payload dans
    QdrantVectorStore). Si une cle est renommee, ce helper est le seul a modifier.

    Args:
        chunk: Payload d'un chunk Qdrant (typiquement `chunks[0]`).

    Returns:
        Dictionnaire avec filename, title, author, total_pages, ingested_at, file_hash.
    """
    return {
        "filename": chunk.get("doc_filename"),
        "title": chunk.get("doc_title"),
        "author": chunk.get("doc_author"),
        "total_pages": chunk.get("doc_total_pages"),
        "ingested_at": chunk.get("ingested_at"),
        "file_hash": chunk.get("doc_file_hash"),
    }
