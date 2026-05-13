# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Construction des payloads Qdrant a partir des DocumentChunk.

Extrait de QdrantVectorStore pour reduire le LOC du store principal.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from src.models.chunk import DocumentChunk
from src.models.document import DocumentMetadata
from src.models.unified import UnifiedMetadata


def generate_point_id(chunk_id: str) -> int:
    """Genere un ID numerique reproductible a partir du chunk_id.

    Utilise MD5 pour rester deterministe (permet l'upsert).

    Args:
        chunk_id: Identifiant unique du chunk.

    Returns:
        Identifiant numerique positif pour Qdrant.
    """
    hash_bytes = hashlib.md5(chunk_id.encode()).hexdigest()[:16]
    return int(hash_bytes, 16)


def build_payload(chunk: DocumentChunk, doc_meta: DocumentMetadata) -> dict[str, Any]:
    """Construit le payload Qdrant pour un chunk PDF."""
    payload = _build_common_payload(chunk)
    payload.update(
        {
            "doc_filename": doc_meta.filename,
            "doc_title": doc_meta.title or "",
            "doc_author": doc_meta.author or "",
            "doc_total_pages": doc_meta.total_pages,
            "doc_file_hash": doc_meta.file_hash,
            "ingested_at": doc_meta.ingested_at.isoformat(),
            "doc_creation_date": (
                doc_meta.creation_date.isoformat() if doc_meta.creation_date else None
            ),
        }
    )
    return payload


def build_unified_payload(chunk: DocumentChunk, unified_meta: UnifiedMetadata) -> dict[str, Any]:
    """Construit le payload Qdrant pour un chunk unifie (Excel/Word)."""
    payload = _build_common_payload(chunk)
    payload.update(
        {
            "document_type": unified_meta.document_type.value,
            "has_formula": unified_meta.has_formulas,
            "sheet_names": unified_meta.sheet_names,
            "doc_filename": unified_meta.filename,
            "doc_title": unified_meta.title or "",
            "doc_author": unified_meta.author or "",
            "doc_total_pages": unified_meta.page_count or 0,
            "doc_file_hash": unified_meta.file_hash,
            "ingested_at": unified_meta.indexed_at.isoformat(),
            "doc_creation_date": (
                unified_meta.created_at.isoformat() if unified_meta.created_at else None
            ),
        }
    )
    return payload


def _build_common_payload(chunk: DocumentChunk) -> dict[str, Any]:
    """Construit la partie commune du payload (chunk + contenu + stats)."""
    meta = chunk.metadata
    content = _sanitize_text(chunk.content)

    return {
        "chunk_id": meta.chunk_id,
        "document_id": meta.document_id,
        "parent_chunk_id": meta.parent_chunk_id or "",
        "content": content,
        "content_preview": content[:500] if content else "",
        "page_numbers": meta.page_numbers,
        "start_page": meta.start_page,
        "end_page": meta.end_page,
        "chunk_index": meta.chunk_index,
        "total_chunks": meta.total_chunks,
        "section_title": meta.section_title or "",
        "section_hierarchy": meta.section_hierarchy,
        "content_type": meta.content_type,
        "has_table": meta.has_table,
        "has_image": meta.has_image,
        "has_equation": meta.has_equation,
        "token_count": meta.token_count,
        "char_count": meta.char_count,
        "word_count": meta.word_count,
        "preceding_context": meta.preceding_context,
        "following_context": meta.following_context,
    }


def _sanitize_text(text: str | None) -> str:
    """Nettoie le texte des caracteres Unicode problematiques.

    Remplace le caractere de remplacement et normalise les espaces / controle.
    """
    if not text:
        return ""

    text = text.replace("�", "")
    text = re.sub(r"\s+", " ", text)
    text = "".join(
        char
        for char in text
        if char in ("\n", "\t", "\r") or (ord(char) >= 32 and ord(char) != 127)
    )

    return text.strip()
