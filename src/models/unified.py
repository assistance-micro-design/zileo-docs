# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Modèles unifiés pour traitement multi-format (PDF, Excel, Word)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.types import CellValue, FormulaResult


class DocumentType(str, Enum):
    """Type de document source."""

    PDF = "pdf"
    EXCEL = "excel"
    WORD = "word"


class TableData(BaseModel):
    """Tableau normalisé (commun à tous les formats)."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[CellValue]] = Field(default_factory=list)
    source_location: str | None = Field(
        None,
        description="Localisation source (page PDF, feuille Excel, etc.)",
    )

    def to_markdown(self) -> str:
        """Convertit en Markdown."""
        if not self.headers and not self.rows:
            return ""

        lines: list[str] = []
        headers = self.headers or (
            [f"Col{i + 1}" for i in range(len(self.rows[0]))] if self.rows else []
        )

        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")

        for row in self.rows:
            cells = [str(cell) if cell is not None else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, list[str] | list[list[str]] | str | None]:
        """Pour stockage Qdrant."""
        return {
            "headers": self.headers,
            "rows": [[str(c) if c is not None else "" for c in row] for row in self.rows],
            "source_location": self.source_location,
        }


class FormulaData(BaseModel):
    """Formule Excel normalisée."""

    cell: str = Field(..., description="Référence cellule (ex: C10)")
    sheet: str = Field(..., description="Nom de la feuille")
    formula: str = Field(..., description="Formule brute")
    result: FormulaResult = Field(None, description="Résultat calculé")
    dependencies: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, str | list[str] | None]:
        """Pour stockage Qdrant."""
        return {
            "cell": self.cell,
            "sheet": self.sheet,
            "formula": self.formula,
            "result": str(self.result) if self.result is not None else None,
            "dependencies": self.dependencies,
        }


class ImageData(BaseModel):
    """Image normalisée."""

    filename: str
    content_type: str
    size_kb: float
    has_base64: bool = Field(
        False,
        description="Si True, données disponibles séparément",
    )
    alt_text: str | None = None
    source_location: str | None = None


class StructuredData(BaseModel):
    """Données structurées extraites du document."""

    tables: list[TableData] = Field(default_factory=list)
    formulas: list[FormulaData] = Field(
        default_factory=list,
        description="Formules Excel uniquement",
    )
    images: list[ImageData] = Field(default_factory=list)

    @property
    def tables_count(self) -> int:
        """Nombre de tableaux."""
        return len(self.tables)

    @property
    def formulas_count(self) -> int:
        """Nombre de formules."""
        return len(self.formulas)

    @property
    def images_count(self) -> int:
        """Nombre d'images."""
        return len(self.images)

    def to_dict(self) -> dict[str, Any]:
        """Pour stockage Qdrant."""
        return {
            "tables": [t.to_dict() for t in self.tables],
            "formulas": [f.to_dict() for f in self.formulas],
            "images_count": self.images_count,
        }


class UnifiedMetadata(BaseModel):
    """Métadonnées unifiées pour tous les documents."""

    # Identifiants
    document_id: str = Field(default_factory=lambda: str(uuid4()))

    # Informations fichier
    filename: str
    file_path: str
    file_size_bytes: int = 0

    # Type et format
    document_type: DocumentType
    original_format: str = Field(..., description="Extension originale (.pdf, .xlsx, etc.)")

    # Contenu
    page_count: int | None = Field(None, description="Pages (PDF) ou feuilles (Excel)")
    word_count: int = 0
    char_count: int = 0

    # Drapeaux
    has_tables: bool = False
    has_images: bool = False
    has_formulas: bool = False  # Excel uniquement
    has_ocr_content: bool = False  # PDF uniquement

    # Propriétés document
    title: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None

    # Spécifique Excel
    sheet_names: list[str] = Field(default_factory=list)

    # Timestamps traitement
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Pour stockage Qdrant."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "document_type": self.document_type.value,
            "original_format": self.original_format,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "has_tables": self.has_tables,
            "has_images": self.has_images,
            "has_formulas": self.has_formulas,
            "has_ocr_content": self.has_ocr_content,
            "title": self.title,
            "author": self.author,
            "sheet_names": self.sheet_names,
            "indexed_at": self.indexed_at.isoformat(),
        }


class UnifiedDocument(BaseModel):
    """Document unifié prêt pour chunking et indexation."""

    # Métadonnées
    metadata: UnifiedMetadata

    # Contenu textuel (pour embedding)
    content_markdown: str = Field(
        ...,
        description="Contenu complet en Markdown",
    )

    # Données structurées
    structured_data: StructuredData = Field(default_factory=StructuredData)

    @property
    def document_id(self) -> str:
        """Identifiant unique du document."""
        return self.metadata.document_id

    @property
    def document_type(self) -> DocumentType:
        """Type de document."""
        return self.metadata.document_type

    @property
    def filename(self) -> str:
        """Nom du fichier."""
        return self.metadata.filename

    def get_chunks_metadata_base(self) -> dict[str, Any]:
        """Retourne les métadonnées de base pour tous les chunks."""
        return {
            "document_id": self.document_id,
            "doc_filename": self.filename,
            "document_type": self.document_type.value,
            "has_table": self.metadata.has_tables,
            "has_image": self.metadata.has_images,
            "has_formula": self.metadata.has_formulas,
        }
