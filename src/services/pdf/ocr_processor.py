# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Phase 3: Processeur OCR avec Mistral.

Traite les pages complexes (tableaux, images, scans) avec Mistral OCR.
"""

from __future__ import annotations

import asyncio
import base64
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import fitz  # PyMuPDF
from mistralai import Mistral

from src.core.config import settings
from src.core.exceptions import OCRAPIError, OCRRateLimitError
from src.models.extraction import (
    ChartData,
    EquationData,
    ImageData,
    OCRResult,
    TableData,
)


class OCRImageProtocol(Protocol):
    """Protocol pour une image dans la reponse OCR Mistral."""

    description: str
    bbox: list[float] | None
    base64: str | None


class OCRPageProtocol(Protocol):
    """Protocol pour une page dans la reponse OCR Mistral."""

    markdown: str
    images: Sequence[OCRImageProtocol]


class OCRResponseProtocol(Protocol):
    """Protocol pour la reponse de l'API OCR Mistral."""

    pages: Sequence[OCRPageProtocol]


class MistralOCRProcessor:
    """Phase 3: Traitement OCR avec Mistral.

    Traite les pages complexes (scannees, avec tableaux, images, graphiques)
    en utilisant l'API Mistral OCR.

    Attributes:
        client: Client Mistral API.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialise le processeur OCR.

        Args:
            api_key: Cle API Mistral. Utilise settings si non fournie.
        """
        self._api_key = api_key or settings.MISTRAL_API_KEY
        self.client = Mistral(api_key=self._api_key)
        self._max_concurrent = settings.OCR_MAX_CONCURRENT
        self._dpi = settings.OCR_DPI
        self._ocr_model = settings.MISTRAL_OCR_MODEL

    async def process_pages(
        self,
        pdf_path: str | Path,
        page_numbers: list[int],
        options: dict[str, Any] | None = None,
    ) -> dict[int, OCRResult]:
        """Traite les pages avec Mistral OCR.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            page_numbers: Liste des numeros de pages a traiter (0-indexed).
            options: Options de traitement optionnelles.

        Returns:
            Dictionnaire {page_number: OCRResult}.
        """
        pdf_path = Path(pdf_path)
        options = options or {}

        # Semaphore pour limiter la concurrence
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def process_with_limit(page_num: int) -> OCRResult:
            async with semaphore:
                return await self._process_single_page(pdf_path, page_num, options)

        # Traitement parallele avec limite
        tasks = [process_with_limit(pn) for pn in page_numbers]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Construire le dictionnaire de resultats
        results: dict[int, OCRResult] = {}
        for page_num, result in zip(page_numbers, results_list, strict=True):
            if isinstance(result, BaseException):
                results[page_num] = self._create_error_result(page_num, str(result))
                continue
            results[page_num] = result

        return results

    async def _process_single_page(
        self,
        pdf_path: Path,
        page_num: int,
        options: dict[str, Any],
    ) -> OCRResult:
        """Traite une page avec OCR.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            page_num: Numero de la page (0-indexed).
            options: Options de traitement.

        Returns:
            OCRResult avec le contenu extrait.
        """
        start_time = time.time()

        # 1. Convertir page en image PNG haute resolution
        img_base64 = self._page_to_base64(pdf_path, page_num)

        # 2. Options Mistral OCR
        table_format = options.get("table_format", settings.OCR_TABLE_FORMAT)
        include_image_base64 = options.get("include_image_base64", False)

        # 3. Appel API Mistral OCR
        try:
            ocr_response = await self._call_ocr_api(img_base64)
        except Exception as e:
            return self._create_error_result(page_num, str(e))

        processing_time = int((time.time() - start_time) * 1000)

        # 4. Parser la reponse
        if not ocr_response or not hasattr(ocr_response, "pages") or not ocr_response.pages:
            return self._create_empty_result(page_num, processing_time)

        page_content = ocr_response.pages[0]
        markdown = getattr(page_content, "markdown", "")

        # 5. Extraire elements structures
        tables = self._extract_tables(markdown, table_format)
        images = self._extract_images(page_content, include_image_base64)
        charts = self._detect_charts(markdown)
        equations = self._extract_equations(markdown)

        return OCRResult(
            page_number=page_num,
            markdown_content=markdown,
            tables=tables,
            images=images,
            charts=charts,
            equations=equations,
            confidence_score=0.95,
            processing_time_ms=processing_time,
        )

    async def _call_ocr_api(
        self,
        img_base64: str,
    ) -> OCRResponseProtocol | None:
        """Appelle l'API Mistral OCR.

        Args:
            img_base64: Image encodee en base64.

        Returns:
            Reponse de l'API OCR.

        Raises:
            OCRRateLimitError: Si rate limit atteint.
            OCRAPIError: Si erreur API.
        """
        try:
            # Utiliser l'API Mistral OCR dediee
            return await asyncio.to_thread(
                self.client.ocr.process,
                model=self._ocr_model,
                document={
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{img_base64}",
                },
                include_image_base64=False,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise OCRRateLimitError() from e
            raise OCRAPIError(500, str(e)) from e

    def _page_to_base64(self, pdf_path: Path, page_num: int) -> str:
        """Convertit une page PDF en image base64.

        Args:
            pdf_path: Chemin vers le fichier PDF.
            page_num: Numero de la page (0-indexed).

        Returns:
            Image encodee en base64.
        """
        doc = fitz.open(pdf_path)
        try:
            page = doc[page_num]

            # Matrice pour DPI configure
            zoom = self._dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            # Render en PNG
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            return base64.b64encode(img_bytes).decode()
        finally:
            doc.close()

    def _extract_tables(
        self,
        markdown: str,
        table_format: str,
    ) -> list[TableData]:
        """Extrait et structure les tableaux.

        Args:
            markdown: Contenu Markdown.
            table_format: Format attendu (markdown/html).

        Returns:
            Liste des TableData extraits.
        """
        tables: list[TableData] = []

        if table_format == "markdown":
            pattern = r"(\|.+\|\n\|[-:| ]+\|\n(?:\|.+\|\n?)+)"

            for i, match in enumerate(re.finditer(pattern, markdown)):
                table_md = match.group(1)
                rows = table_md.strip().split("\n")

                # Parse headers
                header_row = rows[0]
                headers = [h.strip() for h in header_row.split("|")[1:-1]]

                # Parse data
                data_rows: list[list[str]] = []
                for row in rows[2:]:  # Skip header + separator
                    cells = [c.strip() for c in row.split("|")[1:-1]]
                    data_rows.append(cells)

                tables.append(
                    TableData(
                        id=f"table_{i}",
                        markdown=table_md,
                        html=self._md_table_to_html(table_md),
                        headers=headers,
                        rows=len(data_rows),
                        cols=len(headers),
                        data=data_rows,
                    )
                )

        elif table_format == "html":
            pattern = r"<table[^>]*>.*?</table>"

            for i, match in enumerate(re.finditer(pattern, markdown, re.DOTALL)):
                html = match.group()
                tables.append(
                    TableData(
                        id=f"table_{i}",
                        markdown="",
                        html=html,
                        headers=[],
                        rows=html.count("<tr"),
                        cols=0,
                        data=[],
                    )
                )

        return tables

    def _extract_images(
        self,
        page_content: OCRPageProtocol,
        include_base64: bool,
    ) -> list[ImageData]:
        """Extrait informations sur les images.

        Args:
            page_content: Contenu de la page OCR.
            include_base64: Inclure les images en base64.

        Returns:
            Liste des ImageData extraits.
        """
        images: list[ImageData] = []

        if hasattr(page_content, "images"):
            for i, img in enumerate(page_content.images):
                image_data = ImageData(
                    id=f"image_{i}",
                    description=getattr(img, "description", ""),
                    bounding_box=getattr(img, "bbox", None),
                    base64=getattr(img, "base64", None) if include_base64 else None,
                )
                images.append(image_data)

        return images

    def _detect_charts(self, markdown: str) -> list[ChartData]:
        """Detecte les graphiques (heuristique).

        Args:
            markdown: Contenu Markdown.

        Returns:
            Liste des ChartData detectes.
        """
        charts: list[ChartData] = []
        markdown_lower = markdown.lower()

        chart_keywords: dict[str, list[str]] = {
            "bar": ["bar chart", "histogram", "bar graph"],
            "line": ["line chart", "line graph", "trend line"],
            "pie": ["pie chart", "pie graph", "distribution"],
            "scatter": ["scatter plot", "scatter chart"],
            "flow": ["flowchart", "flow diagram", "process flow"],
        }

        for chart_type, keywords in chart_keywords.items():
            for keyword in keywords:
                if keyword in markdown_lower:
                    charts.append(
                        ChartData(
                            id=f"chart_{len(charts)}",
                            chart_type=chart_type,
                            description=f"Detected {chart_type} chart",
                            data_points=[],
                        )
                    )
                    break

        return charts

    def _extract_equations(self, markdown: str) -> list[EquationData]:
        """Extrait les equations LaTeX.

        Args:
            markdown: Contenu Markdown.

        Returns:
            Liste des EquationData extraites.
        """
        equations: list[EquationData] = []

        # Equations block: $$...$$ (a traiter en premier pour eviter les conflits)
        block_pattern = r"\$\$([^$]+)\$\$"
        for i, match in enumerate(re.finditer(block_pattern, markdown)):
            equations.append(
                EquationData(
                    id=f"eq_block_{i}",
                    latex=match.group(1).strip(),
                    type="block",
                )
            )

        # Equations inline: $...$
        # Exclure les $$ deja traites
        cleaned_md = re.sub(r"\$\$[^$]+\$\$", "", markdown)
        inline_pattern = r"\$([^$]+)\$"
        for i, match in enumerate(re.finditer(inline_pattern, cleaned_md)):
            equations.append(
                EquationData(
                    id=f"eq_inline_{i}",
                    latex=match.group(1).strip(),
                    type="inline",
                )
            )

        return equations

    def _md_table_to_html(self, md_table: str) -> str:
        """Convertit tableau Markdown en HTML.

        Args:
            md_table: Tableau au format Markdown.

        Returns:
            Tableau au format HTML.
        """
        rows = md_table.strip().split("\n")
        html_parts: list[str] = ["<table>"]

        # Header
        if rows:
            headers = [h.strip() for h in rows[0].split("|")[1:-1]]
            html_parts.append("<thead><tr>")
            for h in headers:
                html_parts.append(f"<th>{h}</th>")
            html_parts.append("</tr></thead>")

        # Body
        html_parts.append("<tbody>")
        for row in rows[2:]:  # Skip header and separator
            cells = [c.strip() for c in row.split("|")[1:-1]]
            html_parts.append("<tr>")
            for cell in cells:
                html_parts.append(f"<td>{cell}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")

        return "".join(html_parts)

    def _create_empty_result(
        self,
        page_num: int,
        processing_time: int,
    ) -> OCRResult:
        """Cree un resultat vide.

        Args:
            page_num: Numero de la page.
            processing_time: Temps de traitement en ms.

        Returns:
            OCRResult vide.
        """
        return OCRResult(
            page_number=page_num,
            markdown_content="",
            tables=[],
            images=[],
            charts=[],
            equations=[],
            confidence_score=0.0,
            processing_time_ms=processing_time,
        )

    def _create_error_result(
        self,
        page_num: int,
        error: str,
    ) -> OCRResult:
        """Cree un resultat d'erreur.

        Args:
            page_num: Numero de la page.
            error: Message d'erreur.

        Returns:
            OCRResult avec erreur.
        """
        return OCRResult(
            page_number=page_num,
            markdown_content=f"<!-- OCR Error: {error} -->",
            tables=[],
            images=[],
            charts=[],
            equations=[],
            confidence_score=0.0,
            processing_time_ms=0,
        )
