# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Modèles Pydantic pour l'extraction Word."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HeadingLevel(int, Enum):
    """Niveau de titre Word."""

    BODY = 0  # Paragraphe normal
    HEADING_1 = 1  # Titre 1
    HEADING_2 = 2  # Titre 2
    HEADING_3 = 3  # Titre 3
    HEADING_4 = 4  # Titre 4
    HEADING_5 = 5  # Titre 5
    HEADING_6 = 6  # Titre 6


class ContentType(str, Enum):
    """Type de contenu dans le document."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    LIST = "list"


class WordParagraph(BaseModel):
    """Paragraphe Word avec style et niveau."""

    text: str = Field(..., description="Contenu textuel")
    style: str | None = Field(None, description="Nom du style Word")
    level: HeadingLevel = Field(
        HeadingLevel.BODY,
        description="Niveau de titre (0 = corps)",
    )
    is_bold: bool = Field(False, description="Texte en gras")
    is_italic: bool = Field(False, description="Texte en italique")

    def to_markdown(self) -> str:
        """Convertit en Markdown."""
        if self.level == HeadingLevel.BODY:
            return self.text
        prefix = "#" * self.level.value
        return f"{prefix} {self.text}"


class WordListItem(BaseModel):
    """Élément de liste Word."""

    text: str = Field(..., description="Contenu de l'élément")
    level: int = Field(0, ge=0, description="Niveau d'indentation")
    is_ordered: bool = Field(False, description="Liste numérotée ou à puces")


class WordList(BaseModel):
    """Liste Word (à puces ou numérotée)."""

    items: list[WordListItem] = Field(default_factory=list)
    is_ordered: bool = Field(False, description="Liste numérotée")

    def to_markdown(self) -> str:
        """Convertit la liste en Markdown."""
        lines: list[str] = []
        for i, item in enumerate(self.items):
            indent = "  " * item.level
            prefix = f"{i + 1}." if item.is_ordered or self.is_ordered else "-"
            lines.append(f"{indent}{prefix} {item.text}")
        return "\n".join(lines)


class WordTableCell(BaseModel):
    """Cellule de tableau Word."""

    text: str = Field("", description="Contenu textuel")
    row_span: int = Field(1, ge=1, description="Fusion verticale")
    col_span: int = Field(1, ge=1, description="Fusion horizontale")


class WordTable(BaseModel):
    """Tableau Word."""

    rows: list[list[WordTableCell]] = Field(
        default_factory=list,
        description="Lignes du tableau",
    )
    headers: list[str] | None = Field(
        None,
        description="En-têtes si première ligne distincte",
    )

    @property
    def row_count(self) -> int:
        """Retourne le nombre de lignes."""
        return len(self.rows)

    @property
    def col_count(self) -> int:
        """Retourne le nombre de colonnes."""
        return max(len(row) for row in self.rows) if self.rows else 0

    def to_markdown(self) -> str:
        """Convertit le tableau en Markdown."""
        if not self.rows:
            return ""

        lines: list[str] = []

        # Headers: explicites ou première ligne
        headers = self.headers or [cell.text for cell in self.rows[0]]

        # Data: toutes les lignes si headers explicites, sinon skip première
        data_rows = self.rows if self.headers else self.rows[1:]

        # En-têtes
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")

        # Données
        for row in data_rows:
            cells = [cell.text for cell in row]
            # Compléter si nécessaire
            while len(cells) < len(headers):
                cells.append("")
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire pour stockage."""
        return {
            "headers": self.headers or ([c.text for c in self.rows[0]] if self.rows else []),
            "data": [[c.text for c in row] for row in self.rows],
            "row_count": self.row_count,
            "col_count": self.col_count,
        }


class WordImage(BaseModel):
    """Image extraite d'un document Word."""

    filename: str = Field(..., description="Nom du fichier image")
    content_type: str = Field(..., description="Type MIME (image/png, etc.)")
    data_base64: str = Field(..., description="Données encodées en base64")
    width: int | None = Field(None, description="Largeur en pixels")
    height: int | None = Field(None, description="Hauteur en pixels")
    alt_text: str | None = Field(None, description="Texte alternatif")

    @property
    def size_kb(self) -> float:
        """Taille approximative en KB."""
        return len(self.data_base64) * 3 / 4 / 1024


class ContentBlock(BaseModel):
    """Bloc de contenu générique (pour ordre du document)."""

    content_type: ContentType = Field(..., description="Type de contenu")
    order: int = Field(..., ge=0, description="Position dans le document")
    paragraph: WordParagraph | None = None
    table: WordTable | None = None
    image: WordImage | None = None
    list_content: WordList | None = None

    def to_markdown(self) -> str:
        """Convertit le bloc en Markdown."""
        if self.paragraph:
            return self.paragraph.to_markdown()
        if self.table:
            return self.table.to_markdown()
        if self.list_content:
            return self.list_content.to_markdown()
        if self.image:
            alt = self.image.alt_text or self.image.filename
            return f"![{alt}]({self.image.filename})"
        return ""


class WordDocument(BaseModel):
    """Document Word complet."""

    filename: str = Field(..., description="Nom du fichier")
    file_path: str = Field(..., description="Chemin complet")

    # Contenu ordonné
    content_blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="Blocs de contenu dans l'ordre du document",
    )

    # Accès rapide par type
    paragraphs: list[WordParagraph] = Field(default_factory=list)
    tables: list[WordTable] = Field(default_factory=list)
    images: list[WordImage] = Field(default_factory=list)
    lists: list[WordList] = Field(default_factory=list)

    # Métadonnées
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Métadonnées du document",
    )

    # Statistiques
    word_count: int = Field(0, description="Nombre de mots")
    page_count: int | None = Field(None, description="Nombre de pages estimé")

    def to_markdown(self) -> str:
        """Génère le document complet en Markdown."""
        lines: list[str] = [f"# {self.filename}\n"]

        for block in self.content_blocks:
            md = block.to_markdown()
            if md:
                lines.append(md)
                lines.append("")  # Ligne vide entre blocs

        return "\n".join(lines)

    def get_headings(self) -> list[WordParagraph]:
        """Récupère tous les titres du document."""
        return [p for p in self.paragraphs if p.level != HeadingLevel.BODY]

    def get_table_of_contents(self) -> str:
        """Génère une table des matières."""
        toc_lines: list[str] = ["## Table des matières\n"]

        for heading in self.get_headings():
            indent = "  " * (heading.level.value - 1)
            toc_lines.append(f"{indent}- {heading.text}")

        return "\n".join(toc_lines)
