# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Phase 1: Analyseur de document PDF.

Analyse le document PDF pour classifier chaque page et construire
le plan d'extraction optimal (extraction native vs OCR).
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fitz  # PyMuPDF

from src.core.config import settings
from src.core.exceptions import (
    PDFCorruptedError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    SourceFileNotFoundError,
)
from src.models.document import (
    DocumentAnalysisResult,
    DocumentMetadata,
    PageAnalysis,
    PageType,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


class DocumentAnalyzer:
    """Phase 1: Analyse et classification du document PDF.

    Analyse un document PDF pour:
    - Extraire les metadonnees completes
    - Classifier chaque page selon sa complexite
    - Construire le plan d'extraction optimal

    Attributes:
        pdf_path: Chemin vers le fichier PDF.
    """

    # Configuration
    MIN_TEXT_FOR_NATIVE: int = 50  # Caracteres minimum pour extraction native
    SIGNIFICANT_IMAGE_RATIO: float = 0.05  # 5% de la page minimum
    CHART_DRAWING_THRESHOLD: int = 50  # Nombre de dessins pour detecter un graphique
    CHART_TEXT_MAX_LENGTH: int = 500  # Texte max pour page avec graphiques

    def __init__(
        self,
        pdf_path: str | Path,
        original_filename: str | None = None,
    ) -> None:
        """Initialise l'analyseur.

        Args:
            pdf_path: Chemin vers le fichier PDF a analyser.
            original_filename: Nom de fichier original (si different du path).
        """
        self.pdf_path = Path(pdf_path)
        self.original_filename = original_filename or self.pdf_path.name
        self._doc: fitz.Document | None = None

    async def analyze(self) -> DocumentAnalysisResult:
        """Analyse complete du document PDF.

        Returns:
            DocumentAnalysisResult contenant metadonnees, analyses par page,
            et plan d'extraction.

        Raises:
            SourceFileNotFoundError: Si le fichier n'existe pas.
            PDFCorruptedError: Si le fichier est corrompu.
            PDFTooLargeError: Si le fichier depasse la taille max.
            PDFTooManyPagesError: Si le fichier a trop de pages.
        """
        self._validate_file()
        return await asyncio.to_thread(self._analyze_sync)

    def _analyze_sync(self) -> DocumentAnalysisResult:
        """Analyse synchrone du PDF (appelé via to_thread)."""
        try:
            self._doc = fitz.open(self.pdf_path)

            # Valider nombre de pages
            if len(self._doc) > settings.MAX_PAGES:
                raise PDFTooManyPagesError(
                    str(self.pdf_path),
                    len(self._doc),
                    settings.MAX_PAGES,
                )

            metadata = self._extract_metadata()
            pages = [self._analyze_page(i) for i in range(len(self._doc))]

            metadata.total_pages = len(pages)
            metadata.total_images = sum(p.image_count for p in pages)
            metadata.total_tables = sum(p.table_count for p in pages)

            return self._compute_extraction_plan(metadata, pages)

        except fitz.FileDataError as e:
            raise PDFCorruptedError(str(self.pdf_path), str(e)) from e
        finally:
            if self._doc:
                self._doc.close()
                self._doc = None

    def _compute_extraction_plan(
        self,
        metadata: DocumentMetadata,
        pages: list[PageAnalysis],
    ) -> DocumentAnalysisResult:
        """Construit le plan d'extraction et les estimations."""
        pages_local = [p.page_number for p in pages if p.extraction_method == "pymupdf"]
        pages_ocr = [p.page_number for p in pages if p.extraction_method == "mistral_ocr"]

        return DocumentAnalysisResult(
            metadata=metadata,
            pages=pages,
            pages_for_local_extraction=pages_local,
            pages_for_ocr=pages_ocr,
            estimated_tokens=sum(p.native_text_length // 4 for p in pages),
            estimated_ocr_cost=len(pages_ocr) * 0.002,
            estimated_processing_time_seconds=len(pages_ocr) * 0.5 + len(pages_local) * 0.05,
        )

    def _validate_file(self) -> None:
        """Valide que le fichier existe et respecte les limites.

        Raises:
            SourceFileNotFoundError: Si le fichier n'existe pas.
            PDFTooLargeError: Si le fichier depasse la taille max.
        """
        if not self.pdf_path.exists():
            raise SourceFileNotFoundError(str(self.pdf_path))

        size_mb = self.pdf_path.stat().st_size / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise PDFTooLargeError(
                str(self.pdf_path),
                size_mb,
                settings.MAX_FILE_SIZE_MB,
            )

    def _extract_metadata(self) -> DocumentMetadata:
        """Extrait les metadonnees du PDF.

        Returns:
            DocumentMetadata avec les informations du document.
        """
        if self._doc is None:
            msg = "Document not opened"
            raise RuntimeError(msg)

        meta = self._doc.metadata

        # Hash pour deduplication
        with self.pdf_path.open("rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        return DocumentMetadata(
            document_id=str(uuid.uuid4()),
            file_hash=file_hash,
            filename=self.original_filename,
            file_size_bytes=self.pdf_path.stat().st_size,
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            subject=meta.get("subject") or None,
            creator=meta.get("creator") or None,
            producer=meta.get("producer") or None,
            creation_date=self._parse_pdf_date(meta.get("creationDate")),
            modification_date=self._parse_pdf_date(meta.get("modDate")),
            total_pages=0,
            total_images=0,
            total_tables=0,
            ingested_at=datetime.now(UTC),
            processed_at=None,
        )

    def _analyze_page(self, page_num: int) -> PageAnalysis:
        """Analyse une page individuelle.

        Args:
            page_num: Index de la page (0-indexed).

        Returns:
            PageAnalysis avec les informations de la page.
        """
        if self._doc is None:
            msg = "Document not opened"
            raise RuntimeError(msg)

        page: fitz.Page = self._doc[page_num]
        features = self._extract_page_features(page)

        page_type = self._classify_page(
            has_native_text=features["has_native_text"],
            has_images=features["has_images"],
            has_tables=features["table_count"] > 0,
            has_charts=features["has_charts"],
            image_coverage=features["image_coverage"],
        )

        return PageAnalysis(
            page_number=page_num,
            page_type=page_type,
            has_native_text=features["has_native_text"],
            native_text_length=features["text_length"],
            has_images=features["has_images"],
            image_count=features["image_count"],
            image_coverage_ratio=features["image_coverage"],
            has_tables=features["table_count"] > 0,
            table_count=features["table_count"],
            has_charts=features["has_charts"],
            width=page.rect.width,
            height=page.rect.height,
            rotation=page.rotation,
            extraction_method=self._decide_extraction_method(page_type),
            priority=self._get_priority(page_type),
        )

    def _extract_page_features(self, page: fitz.Page) -> dict[str, Any]:
        """Extrait les features brutes d'une page (texte, images, tableaux, dessins)."""
        text = page.get_text("text")
        text_length = len(text.strip())
        has_native_text = text_length >= self.MIN_TEXT_FOR_NATIVE

        images = page.get_images(full=True)
        significant_images = self._filter_significant_images(page, images)
        image_coverage = self._calculate_image_coverage(page, significant_images)

        tables = page.find_tables()
        table_count = len(tables.tables) if tables else 0

        drawings = page.get_drawings()
        has_charts = (
            len(drawings) > self.CHART_DRAWING_THRESHOLD
            and text_length < self.CHART_TEXT_MAX_LENGTH
        )

        return {
            "text_length": text_length,
            "has_native_text": has_native_text,
            "has_images": len(significant_images) > 0,
            "image_count": len(significant_images),
            "image_coverage": image_coverage,
            "table_count": table_count,
            "has_charts": has_charts,
        }

    def _classify_page(
        self,
        *,
        has_native_text: bool,
        has_images: bool,
        has_tables: bool,
        has_charts: bool,
        image_coverage: float,
    ) -> PageType:
        """Classifie le type de page.

        Args:
            has_native_text: Si la page a du texte natif significatif.
            has_images: Si la page a des images significatives.
            has_tables: Si la page a des tableaux.
            has_charts: Si la page a des graphiques.
            image_coverage: Ratio de couverture par les images.

        Returns:
            PageType correspondant au contenu de la page.
        """
        # Page scannee: peu de texte natif mais beaucoup d'images
        if not has_native_text and image_coverage > 0.8:
            return PageType.SCANNED

        # Page mixte: tableaux + images
        if has_tables and has_images:
            return PageType.MIXED

        # Graphiques detectes
        if has_charts:
            return PageType.HAS_CHARTS

        # Tableaux
        if has_tables:
            return PageType.HAS_TABLES

        # Images significatives
        if has_images and image_coverage > 0.2:
            return PageType.HAS_IMAGES

        # Texte simple
        return PageType.TEXT_ONLY

    def _decide_extraction_method(self, page_type: PageType) -> str:
        """Decide de la methode d'extraction.

        Args:
            page_type: Type de la page.

        Returns:
            "pymupdf" pour extraction native ou "mistral_ocr" pour OCR.
        """
        if page_type in (
            PageType.SCANNED,
            PageType.HAS_TABLES,
            PageType.HAS_CHARTS,
            PageType.HAS_IMAGES,
            PageType.MIXED,
        ):
            return "mistral_ocr"
        return "pymupdf"

    def _filter_significant_images(
        self,
        page: fitz.Page,
        images: Sequence[tuple[int, ...]],
    ) -> list[dict[str, object]]:
        """Filtre les images significatives (> 5% de la page).

        Args:
            page: Page PyMuPDF.
            images: Liste des images de la page.

        Returns:
            Liste des images significatives avec leurs metadonnees.
        """
        page_area = page.rect.width * page.rect.height
        significant: list[dict[str, object]] = []

        for img in images:
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
                for rect in rects:
                    ratio = (rect.width * rect.height) / page_area
                    if ratio > self.SIGNIFICANT_IMAGE_RATIO:
                        significant.append(
                            {
                                "xref": xref,
                                "rect": rect,
                                "ratio": ratio,
                            }
                        )
                        break
            except (ValueError, RuntimeError):
                # Image non trouvee ou erreur de lecture
                continue

        return significant

    def _calculate_image_coverage(
        self,
        page: fitz.Page,
        images: list[dict[str, object]],
    ) -> float:
        """Calcule le pourcentage de couverture par les images.

        Args:
            page: Page PyMuPDF.
            images: Liste des images significatives.

        Returns:
            Ratio de couverture (0.0 - 1.0).
        """
        if not images:
            return 0.0

        page_area: float = page.rect.width * page.rect.height
        total_area = 0.0
        for img in images:
            rect = img["rect"]
            total_area += float(rect.width * rect.height)  # type: ignore[attr-defined]
        return float(min(total_area / page_area, 1.0))

    def _get_priority(self, page_type: PageType) -> int:
        """Retourne la priorite de traitement.

        Args:
            page_type: Type de la page.

        Returns:
            Priorite (1 = plus haute).
        """
        priorities: dict[PageType, int] = {
            PageType.TEXT_ONLY: 1,
            PageType.HAS_TABLES: 2,
            PageType.HAS_IMAGES: 3,
            PageType.HAS_CHARTS: 4,
            PageType.MIXED: 5,
            PageType.SCANNED: 6,
        }
        return priorities.get(page_type, 5)

    def _parse_pdf_date(self, date_str: str | None) -> datetime | None:
        """Parse une date au format PDF (D:YYYYMMDDHHmmSS).

        Args:
            date_str: Chaine de date PDF.

        Returns:
            datetime ou None si parsing impossible.
        """
        if not date_str:
            return None
        try:
            clean_date = date_str
            if clean_date.startswith("D:"):
                clean_date = clean_date[2:]
            # Prendre seulement les 14 premiers caracteres (YYYYMMDDHHMMSS)
            parsed = datetime.strptime(clean_date[:14], "%Y%m%d%H%M%S")
            return parsed.replace(tzinfo=UTC)
        except (ValueError, IndexError):
            return None
