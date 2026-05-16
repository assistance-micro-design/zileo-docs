# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Models pour les chunks de documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.services.embedding.sparse_embedder import SparseEmbeddingData


@dataclass
class ChunkMetadata:
    """Metadata riche pour chaque chunk.

    Attributes:
        chunk_id: Identifiant unique du chunk.
        document_id: Identifiant du document parent.
    """

    # === Identifiants ===
    chunk_id: str
    document_id: str
    parent_chunk_id: str | None = None

    # === Localisation ===
    page_numbers: list[int] = field(default_factory=list)
    start_page: int = 0
    end_page: int = 0

    # === Structure ===
    section_title: str | None = None
    section_hierarchy: list[str] = field(default_factory=list)
    chunk_index: int = 0
    total_chunks: int = 0

    # === Type de contenu ===
    content_type: str = "text"
    has_table: bool = False
    has_image: bool = False
    has_equation: bool = False

    # Type de document
    document_type: str = "pdf"  # pdf, excel, word

    # Spécifique Excel
    sheet_name: str | None = None
    has_formula: bool = False
    formulas: list[dict[str, object]] | None = None

    # Spécifique Word
    heading_level: int | None = None

    # === Statistiques ===
    token_count: int = 0
    char_count: int = 0
    word_count: int = 0

    # === Contexte ===
    preceding_context: str = ""
    following_context: str = ""

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "parent_chunk_id": self.parent_chunk_id,
            "page_numbers": self.page_numbers,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "section_title": self.section_title,
            "section_hierarchy": self.section_hierarchy,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "content_type": self.content_type,
            "has_table": self.has_table,
            "has_image": self.has_image,
            "has_equation": self.has_equation,
            "document_type": self.document_type,
            "sheet_name": self.sheet_name,
            "has_formula": self.has_formula,
            "formulas": self.formulas,
            "heading_level": self.heading_level,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "preceding_context": self.preceding_context,
            "following_context": self.following_context,
        }

    def to_qdrant_payload(self) -> dict[str, object]:
        """Convertit en payload pour Qdrant avec types compatibles.

        Qdrant supporte: str, int, float, bool, list (de scalaires).
        """
        payload: dict[str, object] = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "parent_chunk_id": self.parent_chunk_id or "",
            "page_numbers": self.page_numbers,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "section_title": self.section_title or "",
            "section_hierarchy": self.section_hierarchy,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "content_type": self.content_type,
            "has_table": self.has_table,
            "has_image": self.has_image,
            "has_equation": self.has_equation,
            "document_type": self.document_type,
            "has_formula": self.has_formula,
            "token_count": self.token_count,
            "char_count": self.char_count,
            "word_count": self.word_count,
        }

        # Champs optionnels (évite null dans Qdrant)
        if self.sheet_name:
            payload["sheet_name"] = self.sheet_name
        if self.formulas:
            payload["formulas"] = self.formulas
        if self.heading_level is not None:
            payload["heading_level"] = self.heading_level

        return payload


@dataclass
class DocumentChunk:
    """Chunk pret pour embedding et stockage.

    Attributes:
        content: Contenu textuel du chunk.
        metadata: Metadonnees associees.
    """

    content: str
    metadata: ChunkMetadata
    embedding: list[float] | None = None
    sparse_embedding: SparseEmbeddingData | None = None
    content_with_context: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "embedding": self.embedding,
            "content_with_context": self.content_with_context,
        }

    @property
    def has_embedding(self) -> bool:
        """Indique si le chunk a un embedding."""
        return self.embedding is not None and len(self.embedding) > 0
