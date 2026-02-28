# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Extracteur de contenu pour fichiers Word (.docx)."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any

from docx2python import docx2python

from src.models.word import (
    ContentBlock,
    ContentType,
    HeadingLevel,
    WordDocument,
    WordImage,
    WordList,
    WordParagraph,
    WordTable,
    WordTableCell,
)


logger = logging.getLogger(__name__)


class WordExtractor:
    """Extracteur de contenu pour fichiers Word (.docx).

    Attributes:
        extract_images: Si True, extrait les images en base64.
    """

    def __init__(self, extract_images: bool = True) -> None:
        """Initialise l'extracteur.

        Args:
            extract_images: Si True, extrait les images en base64.
        """
        self.extract_images = extract_images

    async def extract(self, file_path: str | Path) -> WordDocument:
        """Extrait le contenu d'un fichier Word.

        Args:
            file_path: Chemin vers le fichier .docx.

        Returns:
            WordDocument avec contenu structuré.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si le format n'est pas supporté.
        """
        path = Path(file_path)

        if not path.exists():
            msg = f"Fichier non trouvé: {path}"
            raise FileNotFoundError(msg)

        if path.suffix.lower() != ".docx":
            msg = f"Format non supporté: {path.suffix}. Seul .docx est accepté."
            raise ValueError(msg)

        return await self._extract_docx(path)

    async def _extract_docx(self, path: Path) -> WordDocument:
        """Extrait le contenu d'un fichier .docx."""
        doc = docx2python(str(path))

        content_blocks: list[ContentBlock] = []
        paragraphs: list[WordParagraph] = []
        tables: list[WordTable] = []
        images: list[WordImage] = []
        lists: list[WordList] = []

        order = 0
        word_count = 0

        # docx2python structure:
        # body = [section1, section2, ...] où chaque section est soit:
        # - Une section texte: [[[paragraph1, paragraph2, ...]]]
        # - Un tableau: [[row1], [row2], ...] où row = [[cell1], [cell2], ...]
        for section in doc.body:
            # Tables: traitement et continue
            if self._is_table_section(section):
                table = self._extract_table_from_section(section)
                if not table.rows:
                    continue
                tables.append(table)
                content_blocks.append(
                    ContentBlock(
                        content_type=ContentType.TABLE,
                        order=order,
                        table=table,
                    )
                )
                order += 1
                continue

            # Sections texte (plus de else)
            for column in section:
                for cell in column:
                    # cell est une liste de paragraphes
                    if isinstance(cell, list):
                        for para_text in cell:
                            if isinstance(para_text, str) and para_text.strip():
                                para = self._extract_paragraph(para_text)
                                paragraphs.append(para)
                                word_count += len(para_text.split())

                                content_blocks.append(
                                    ContentBlock(
                                        content_type=(
                                            ContentType.HEADING
                                            if para.level != HeadingLevel.BODY
                                            else ContentType.PARAGRAPH
                                        ),
                                        order=order,
                                        paragraph=para,
                                    )
                                )
                                order += 1

        # Extraire les images
        if self.extract_images and doc.images:
            for img_name, img_data in doc.images.items():
                image = self._process_image(img_name, img_data)
                if image:
                    images.append(image)
                    content_blocks.append(
                        ContentBlock(
                            content_type=ContentType.IMAGE,
                            order=order,
                            image=image,
                        )
                    )
                    order += 1

        # Métadonnées
        metadata = self._extract_metadata(doc)

        return WordDocument(
            filename=path.name,
            file_path=str(path.absolute()),
            content_blocks=content_blocks,
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            lists=lists,
            metadata=metadata,
            word_count=word_count,
        )

    def _is_table_section(self, section: list[Any]) -> bool:
        """Détermine si une section est un tableau.

        Les tableaux ont une structure où chaque ligne est une liste de cellules,
        et chaque cellule est une liste de paragraphes.
        Une section texte normale a une structure [[[para1, para2, ...]]]
        """
        if not section or not isinstance(section, list):
            return False

        # Un tableau a plusieurs lignes, chacune avec plusieurs cellules
        # Une section texte a généralement une seule colonne avec une seule cellule
        if len(section) <= 1:
            return False

        # Vérifier si c'est une structure de tableau (lignes avec cellules)
        # Plusieurs cellules par ligne = probablement un tableau
        first_row = section[0]
        return isinstance(first_row, list) and len(first_row) > 1

    def _extract_table_from_section(self, section: list[Any]) -> WordTable:
        """Extrait un tableau à partir d'une section docx2python."""
        rows: list[list[WordTableCell]] = []

        for row in section:
            cells: list[WordTableCell] = []
            for cell in row:
                # cell est une liste de paragraphes (docx2python) ou une valeur scalaire
                text = (
                    "\n".join(str(p) for p in cell if p)
                    if isinstance(cell, list)
                    else (str(cell) if cell else "")
                )
                cells.append(WordTableCell(text=text.strip()))

            if cells:
                rows.append(cells)

        return WordTable(rows=rows)

    def _extract_paragraph(self, text: str) -> WordParagraph:
        """Extrait un paragraphe et détecte son niveau.

        Args:
            text: Texte brut du paragraphe.

        Returns:
            WordParagraph avec niveau de titre détecté.
        """
        # Nettoyer le texte
        clean_text = text.strip()

        # Détecter le niveau de titre (heuristique basée sur le style)
        # docx2python ne préserve pas directement les styles,
        # on utilise des patterns
        level = HeadingLevel.BODY

        # Pattern pour détecter les titres numérotés
        heading_patterns: list[tuple[str, HeadingLevel]] = [
            (r"^#{1}\s", HeadingLevel.HEADING_1),
            (r"^#{2}\s", HeadingLevel.HEADING_2),
            (r"^#{3}\s", HeadingLevel.HEADING_3),
            (r"^\d+\.\s+[A-Z]", HeadingLevel.HEADING_1),  # "1. Titre"
            (r"^\d+\.\d+\.\s+", HeadingLevel.HEADING_2),  # "1.1. Sous-titre"
            (r"^\d+\.\d+\.\d+\.\s+", HeadingLevel.HEADING_3),  # "1.1.1. ..."
        ]

        for pattern, heading_level in heading_patterns:
            if re.match(pattern, clean_text):
                level = heading_level
                # Nettoyer le préfixe markdown si présent
                clean_text = re.sub(r"^#+\s+", "", clean_text)
                break

        return WordParagraph(
            text=clean_text,
            level=level,
        )

    def _process_image(
        self,
        name: str,
        data: bytes,
    ) -> WordImage | None:
        """Traite une image extraite.

        Args:
            name: Nom du fichier image.
            data: Données binaires de l'image.

        Returns:
            WordImage ou None si les données sont vides.
        """
        if not data:
            return None

        # Détecter le type MIME
        content_type = "image/png"  # Défaut
        name_lower = name.lower()
        if name_lower.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif name_lower.endswith(".gif"):
            content_type = "image/gif"
        elif name_lower.endswith(".bmp"):
            content_type = "image/bmp"

        # Encoder en base64
        data_b64 = base64.b64encode(data).decode("utf-8")

        return WordImage(
            filename=name,
            content_type=content_type,
            data_base64=data_b64,
        )

    def _extract_metadata(self, doc: Any) -> dict[str, Any]:
        """Extrait les métadonnées du document.

        Args:
            doc: Document docx2python.

        Returns:
            Dictionnaire de métadonnées.
        """
        metadata: dict[str, Any] = {}

        # docx2python v3+ uses core_properties instead of properties
        props = getattr(doc, "core_properties", None) or getattr(doc, "properties", None)
        if props and isinstance(props, dict):
            metadata = {
                "title": props.get("title"),
                "author": props.get("creator"),
                "subject": props.get("subject"),
                "keywords": props.get("keywords"),
                "created": props.get("created"),
                "modified": props.get("modified"),
            }
        elif props:
            metadata = {
                "title": getattr(props, "title", None),
                "author": getattr(props, "creator", None),
                "subject": getattr(props, "subject", None),
                "keywords": getattr(props, "keywords", None),
                "created": str(getattr(props, "created", "")) or None,
                "modified": str(getattr(props, "modified", "")) or None,
            }
            # Nettoyer les None
            metadata = {k: v for k, v in metadata.items() if v}

        return metadata
