"""Phase 2: Extracteur de contenu natif avec PyMuPDF4LLM.

Extrait le contenu texte des pages simples (TEXT_ONLY) en Markdown structure.
"""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf4llm

from src.models.extraction import (
    ExtractedContent,
    HeaderInfo,
    ImagePlaceholder,
    ListInfo,
    TablePlaceholder,
)


class NativeContentExtractor:
    """Phase 2: Extraction contenu natif avec PyMuPDF4LLM.

    Extrait le contenu des pages simples (TEXT_ONLY) en utilisant
    PyMuPDF4LLM pour generer du Markdown structure.

    Attributes:
        pdf_path: Chemin vers le fichier PDF.
    """

    def __init__(self, pdf_path: str | Path) -> None:
        """Initialise l'extracteur.

        Args:
            pdf_path: Chemin vers le fichier PDF.
        """
        self.pdf_path = Path(pdf_path)

    async def extract_pages(
        self,
        page_numbers: list[int],
    ) -> dict[int, ExtractedContent]:
        """Extrait le contenu des pages specifiees.

        Args:
            page_numbers: Liste des numeros de pages a extraire (0-indexed).

        Returns:
            Dictionnaire {page_number: ExtractedContent}.
        """
        results: dict[int, ExtractedContent] = {}

        for page_num in page_numbers:
            content = await self._extract_single_page(page_num)
            results[page_num] = content

        return results

    async def _extract_single_page(self, page_num: int) -> ExtractedContent:
        """Extrait le contenu d'une page.

        Args:
            page_num: Numero de la page (0-indexed).

        Returns:
            ExtractedContent avec le contenu Markdown et structure.
        """
        # Extraction Markdown avec PyMuPDF4LLM
        md_content = pymupdf4llm.to_markdown(
            str(self.pdf_path),
            pages=[page_num],
            show_progress=False,
            page_chunks=False,
            write_images=False,
        )

        # Normaliser le contenu (peut etre une liste si page_chunks=True)
        if isinstance(md_content, list):
            md_content = "\n".join(md_content)

        # Analyse de la structure
        headers = self._extract_headers(md_content)
        paragraphs = self._extract_paragraphs(md_content)
        lists = self._extract_lists(md_content)

        # Detection placeholders
        table_placeholders = self._detect_tables(md_content)
        image_placeholders = self._detect_images(md_content)

        return ExtractedContent(
            page_number=page_num,
            markdown_content=md_content,
            extraction_method="pymupdf4llm",
            headers=headers,
            paragraphs=paragraphs,
            lists=lists,
            table_placeholders=table_placeholders,
            image_placeholders=image_placeholders,
            char_count=len(md_content),
            word_count=len(md_content.split()),
        )

    def _extract_headers(self, md: str) -> list[HeaderInfo]:
        """Extrait les titres Markdown.

        Args:
            md: Contenu Markdown.

        Returns:
            Liste des headers detectes.
        """
        headers: list[HeaderInfo] = []
        pattern = r"^(#{1,6})\s+(.+)$"

        for match in re.finditer(pattern, md, re.MULTILINE):
            headers.append(
                HeaderInfo(
                    level=len(match.group(1)),
                    text=match.group(2).strip(),
                    position=match.start(),
                )
            )

        return headers

    def _extract_paragraphs(self, md: str) -> list[str]:
        """Extrait les paragraphes.

        Args:
            md: Contenu Markdown.

        Returns:
            Liste des paragraphes.
        """
        # Split par lignes vides
        blocks = re.split(r"\n\n+", md)
        paragraphs: list[str] = []

        for raw_block in blocks:
            stripped_block = raw_block.strip()
            # Exclure headers, listes, tableaux
            if not stripped_block:
                continue
            if stripped_block.startswith("#"):
                continue
            if stripped_block.startswith(("-", "*", "1.")):
                continue
            if stripped_block.startswith("|"):
                continue
            if stripped_block.startswith("```"):
                continue

            paragraphs.append(stripped_block)

        return paragraphs

    def _extract_lists(self, md: str) -> list[ListInfo]:
        """Extrait les listes.

        Args:
            md: Contenu Markdown.

        Returns:
            Liste des ListInfo detectees.
        """
        lists: list[ListInfo] = []

        # Listes a puces
        bullet_pattern = r"(?:^[-*]\s+.+$\n?)+"
        for match in re.finditer(bullet_pattern, md, re.MULTILINE):
            items = [
                line.lstrip("-* ").strip()
                for line in match.group().strip().split("\n")
                if line.strip()
            ]
            if items:
                lists.append(ListInfo(type="bullet", items=items))

        # Listes numerotees
        numbered_pattern = r"(?:^\d+\.\s+.+$\n?)+"
        for match in re.finditer(numbered_pattern, md, re.MULTILINE):
            items = [
                re.sub(r"^\d+\.\s*", "", line).strip()
                for line in match.group().strip().split("\n")
                if line.strip()
            ]
            if items:
                lists.append(ListInfo(type="numbered", items=items))

        return lists

    def _detect_tables(self, md: str) -> list[TablePlaceholder]:
        """Detecte les tableaux Markdown.

        Args:
            md: Contenu Markdown.

        Returns:
            Liste des TablePlaceholder detectes.
        """
        placeholders: list[TablePlaceholder] = []
        # Pattern pour tableaux Markdown
        pattern = r"\|.+\|\n\|[-:| ]+\|\n(?:\|.+\|\n?)+"

        for i, match in enumerate(re.finditer(pattern, md)):
            rows = match.group().strip().split("\n")
            # Nombre de colonnes depuis la premiere ligne
            cols = len(rows[0].split("|")) - 2  # -2 pour les | vides aux extremites

            placeholders.append(
                TablePlaceholder(
                    id=f"table_{i}",
                    position=match.start(),
                    rows=len(rows) - 1,  # -1 pour le separateur
                    cols=max(cols, 0),
                    raw_content=match.group(),
                )
            )

        return placeholders

    def _detect_images(self, md: str) -> list[ImagePlaceholder]:
        """Detecte les references images.

        Args:
            md: Contenu Markdown.

        Returns:
            Liste des ImagePlaceholder detectes.
        """
        placeholders: list[ImagePlaceholder] = []
        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

        for i, match in enumerate(re.finditer(pattern, md)):
            placeholders.append(
                ImagePlaceholder(
                    id=f"image_{i}",
                    position=match.start(),
                    alt_text=match.group(1),
                    path=match.group(2),
                )
            )

        return placeholders
