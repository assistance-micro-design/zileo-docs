# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Generateur de presentations PowerPoint (.pptx)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm, Pt

from src.core.config import settings
from src.core.exceptions import (
    PresentationChartError,
    PresentationGenerationError,
    PresentationImageNotFoundError,
    PresentationOutputTooLargeError,
    PresentationTemplateNotFoundError,
)
from src.models.api import CreatePresentationParams, CreatePresentationResult
from src.models.presentation_generation import (
    BulletItem,
    ChartSlideDef,
    ClosingSlideDef,
    ContentBulletsSlideDef,
    ContentWithImageSlideDef,
    ImageDef,
    ImageFullSlideDef,
    PresentationChartDef,
    SectionHeaderSlideDef,
    TextStyle,
    TitleSlideDef,
    TwoColumnsSlideDef,
)


if TYPE_CHECKING:
    from pptx.slide import Slide
    from pptx.text.text import TextFrame

logger = logging.getLogger(__name__)


# Mapping noms simplifies -> enums python-pptx (XY_SCATTER utilise car SCATTER n'existe pas)
_CHART_TYPE_MAP: dict[str, Any] = {
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
    "area": XL_CHART_TYPE.AREA,
    "scatter": XL_CHART_TYPE.XY_SCATTER,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
}

# Index du layout "Blank" dans la collection par defaut de python-pptx
_BLANK_LAYOUT_INDEX = 6


class PresentationGenerator:
    """Genere des presentations PowerPoint a partir de definitions structurees.

    Utilise python-pptx pour creer des fichiers .pptx avec slides,
    texte, images, graphiques et notes.

    Attributes:
        _output_path: Repertoire de sortie des fichiers generes.
        _images_path: Repertoire des images disponibles.
        _templates_path: Repertoire des templates disponibles.
    """

    def __init__(
        self,
        output_path: Path | None = None,
        images_path: Path | None = None,
        templates_path: Path | None = None,
    ) -> None:
        """Initialise le generateur.

        Args:
            output_path: Repertoire de sortie (defaut: settings.OUTPUT_PATH).
            images_path: Repertoire des images (defaut: settings.IMAGES_POWERPOINT_PATH).
            templates_path: Repertoire des templates (defaut: settings.TEMPLATES_PPTX_PATH).
        """
        self._output_path = Path(output_path or settings.OUTPUT_PATH)
        self._images_path = Path(images_path or settings.IMAGES_POWERPOINT_PATH)
        self._templates_path = Path(templates_path or settings.TEMPLATES_PPTX_PATH)
        self._max_output_size_mb = settings.MAX_OUTPUT_FILE_SIZE_MB

    async def generate(self, params: CreatePresentationParams) -> CreatePresentationResult:
        """Point d'entree principal. Cree le fichier pptx.

        Args:
            params: Parametres de creation de la presentation.

        Returns:
            Resultat avec chemin, stats et taille du fichier.
        """
        return await asyncio.to_thread(self._generate_sync, params)

    def _generate_sync(self, params: CreatePresentationParams) -> CreatePresentationResult:
        """Generation synchrone du fichier (appelee via to_thread).

        Returns:
            Resultat avec chemin, stats et taille du fichier.
        """
        self.ensure_output_dir()
        safe_filename = self.sanitize_filename(params.filename)
        file_path = self._output_path / safe_filename
        overwritten = file_path.exists()

        prs = self._load_or_create_presentation(params.template)
        total_images, total_charts = self._process_slides(prs, params.slides)

        if params.author:
            prs.core_properties.author = params.author

        file_size = self.save_and_verify(prs, file_path, safe_filename)

        logger.info(
            "Presentation generee: %s (%d slides, %d images, %d charts, %d octets)",
            safe_filename,
            len(params.slides),
            total_images,
            total_charts,
            file_size,
        )

        return CreatePresentationResult(
            file_path=str(file_path),
            filename=safe_filename,
            slides_created=len(params.slides),
            total_images=total_images,
            total_charts=total_charts,
            file_size_bytes=file_size,
            overwritten=overwritten,
        )

    def _load_or_create_presentation(self, template: str | None) -> Presentation:
        """Charge un template ou cree une presentation vierge.

        Args:
            template: Nom du fichier template (optionnel).

        Returns:
            Instance Presentation.

        Raises:
            PresentationTemplateNotFoundError: Si le template est introuvable.
        """
        if not template:
            return Presentation()

        if ".." in template or "/" in template or "\\" in template:
            raise PresentationGenerationError(
                message=f"Nom de template invalide: {template}",
                code="INVALID_TEMPLATE_NAME",
                suggestion="Le nom du template ne doit pas contenir '..' , '/' ou '\\'.",
                parameter="template",
                retry=True,
            )

        template_path = self._templates_path / template
        if not template_path.exists():
            available = self._list_templates()
            raise PresentationTemplateNotFoundError(template, available)
        return Presentation(str(template_path))

    def _list_templates(self) -> list[str]:
        """Liste les templates disponibles."""
        if not self._templates_path.exists():
            return []
        return sorted(f.name for f in self._templates_path.glob("*.pptx"))

    def _process_slides(self, prs: Presentation, slides: list[Any]) -> tuple[int, int]:
        """Cree tous les slides de la presentation.

        Args:
            prs: Presentation python-pptx cible.
            slides: Liste de SlideDef (union discriminee par layout).

        Returns:
            Tuple (total_images, total_charts).
        """
        total_images = 0
        total_charts = 0

        # Layout dispatch table
        slide_handlers: dict[str, Any] = {
            "title_slide": self._create_title_slide,
            "content_bullets": self._create_content_bullets_slide,
            "content_with_image": self._create_content_with_image_slide,
            "section_header": self._create_section_header_slide,
            "two_columns": self._create_two_columns_slide,
            "image_full": self._create_image_full_slide,
            "chart_slide": self._create_chart_slide,
            "closing": self._create_closing_slide,
        }

        for slide_def in slides:
            handler = slide_handlers.get(slide_def.layout)
            if not handler:
                msg = f"Layout inconnu: {slide_def.layout}"
                raise PresentationGenerationError(msg)

            images, charts = handler(prs, slide_def)
            total_images += images
            total_charts += charts

        return total_images, total_charts

    # === Layout Handlers ===

    def _create_title_slide(self, prs: Presentation, slide_def: TitleSlideDef) -> tuple[int, int]:
        """Cree un slide de titre."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(slide, slide_def.title, slide_def.title_style, font_size=44)
        if slide_def.subtitle:
            self._add_subtitle_textbox(slide, slide_def.subtitle)
        self._set_notes(slide, slide_def.notes)
        return 0, 0

    def _create_content_bullets_slide(
        self, prs: Presentation, slide_def: ContentBulletsSlideDef
    ) -> tuple[int, int]:
        """Cree un slide avec liste a puces."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(slide, slide_def.title, slide_def.title_style)
        self._add_bullets_textbox(slide, slide_def.bullets, left_cm=1.5, top_cm=2.5, width_cm=21.0)
        self._set_notes(slide, slide_def.notes)
        return 0, 0

    def _create_content_with_image_slide(
        self, prs: Presentation, slide_def: ContentWithImageSlideDef
    ) -> tuple[int, int]:
        """Cree un slide avec texte et image."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(slide, slide_def.title, slide_def.title_style)
        self._add_bullets_textbox(slide, slide_def.bullets, left_cm=1.0, top_cm=2.5, width_cm=11.0)
        self._add_image_to_slide(slide, slide_def.image, left_cm=13.0, top_cm=2.5)
        self._set_notes(slide, slide_def.notes)
        return 1, 0

    def _create_section_header_slide(
        self, prs: Presentation, slide_def: SectionHeaderSlideDef
    ) -> tuple[int, int]:
        """Cree un slide de transition entre sections."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(
            slide, slide_def.title, slide_def.title_style, top_cm=6.0, font_size=40
        )
        if slide_def.subtitle:
            self._add_subtitle_textbox(slide, slide_def.subtitle, top_cm=9.0)
        self._set_notes(slide, slide_def.notes)
        return 0, 0

    def _create_two_columns_slide(
        self, prs: Presentation, slide_def: TwoColumnsSlideDef
    ) -> tuple[int, int]:
        """Cree un slide a deux colonnes."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(slide, slide_def.title, slide_def.title_style)
        self._add_bullets_textbox(
            slide, slide_def.left_bullets, left_cm=1.0, top_cm=2.5, width_cm=10.5
        )
        self._add_bullets_textbox(
            slide, slide_def.right_bullets, left_cm=12.5, top_cm=2.5, width_cm=10.5
        )
        self._set_notes(slide, slide_def.notes)
        return 0, 0

    def _create_image_full_slide(
        self, prs: Presentation, slide_def: ImageFullSlideDef
    ) -> tuple[int, int]:
        """Cree un slide image pleine page."""
        slide = self._add_blank_slide(prs)
        self._add_image_to_slide(slide, slide_def.image, left_cm=2.0, top_cm=1.5, full_slide=True)
        if slide_def.title:
            self._add_title_textbox(slide, slide_def.title, slide_def.title_style, font_size=28)
        if slide_def.caption:
            self._add_caption_textbox(slide, slide_def.caption)
        self._set_notes(slide, slide_def.notes)
        return 1, 0

    def _create_chart_slide(self, prs: Presentation, slide_def: ChartSlideDef) -> tuple[int, int]:
        """Cree un slide avec graphique."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(slide, slide_def.title, slide_def.title_style)
        try:
            self._add_chart_to_slide(slide, slide_def.chart)
            charts = 1
        except PresentationChartError as exc:
            logger.warning(
                "Graphique ignore '%s': %s",
                slide_def.chart.title or "sans titre",
                str(exc),
            )
            charts = 0
        self._set_notes(slide, slide_def.notes)
        return 0, charts

    def _create_closing_slide(
        self, prs: Presentation, slide_def: ClosingSlideDef
    ) -> tuple[int, int]:
        """Cree un slide de cloture."""
        slide = self._add_blank_slide(prs)
        self._add_title_textbox(
            slide, slide_def.title, slide_def.title_style, top_cm=5.0, font_size=40
        )
        if slide_def.subtitle:
            self._add_subtitle_textbox(slide, slide_def.subtitle, top_cm=8.0)
        if slide_def.bullets:
            self._add_bullets_textbox(
                slide, slide_def.bullets, left_cm=6.0, top_cm=10.0, width_cm=12.0
            )
        self._set_notes(slide, slide_def.notes)
        return 0, 0

    # === Helpers ===

    def _add_blank_slide(self, prs: Presentation) -> Slide:
        """Ajoute un slide vierge a la presentation."""
        layout = prs.slide_layouts[_BLANK_LAYOUT_INDEX]
        return prs.slides.add_slide(layout)

    def _add_title_textbox(
        self,
        slide: Slide,
        title: str,
        style: TextStyle | None = None,
        left_cm: float = 1.5,
        top_cm: float = 0.5,
        width_cm: float = 21.0,
        height_cm: float = 2.0,
        font_size: int = 32,
    ) -> None:
        """Ajoute un titre en textbox sur le slide."""
        txbox = slide.shapes.add_textbox(Cm(left_cm), Cm(top_cm), Cm(width_cm), Cm(height_cm))
        tf = txbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.alignment = PP_ALIGN.LEFT

        effective_size = font_size
        if style and style.font_size:
            effective_size = style.font_size

        run = p.runs[0]
        run.font.size = Pt(effective_size)
        run.font.bold = style.bold if style else False
        if style and style.italic:
            run.font.italic = True
        if style and style.font_color:
            run.font.color.rgb = RGBColor.from_string(style.font_color)

    def _add_subtitle_textbox(
        self,
        slide: Slide,
        subtitle: str,
        top_cm: float = 3.5,
    ) -> None:
        """Ajoute un sous-titre sur le slide."""
        txbox = slide.shapes.add_textbox(Cm(1.5), Cm(top_cm), Cm(21.0), Cm(1.5))
        tf = txbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = subtitle
        p.alignment = PP_ALIGN.LEFT
        run = p.runs[0]
        run.font.size = Pt(20)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    def _add_caption_textbox(self, slide: Slide, caption: str) -> None:
        """Ajoute un texte de legende en bas du slide."""
        txbox = slide.shapes.add_textbox(Cm(1.5), Cm(16.5), Cm(21.0), Cm(1.0))
        tf = txbox.text_frame
        p = tf.paragraphs[0]
        p.text = caption
        p.alignment = PP_ALIGN.CENTER
        run = p.runs[0]
        run.font.size = Pt(12)
        run.font.italic = True
        run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    def _add_bullets_textbox(
        self,
        slide: Slide,
        bullets: list[BulletItem],
        left_cm: float,
        top_cm: float,
        width_cm: float,
        height_cm: float = 12.0,
    ) -> None:
        """Ajoute une zone de texte avec puces."""
        txbox = slide.shapes.add_textbox(Cm(left_cm), Cm(top_cm), Cm(width_cm), Cm(height_cm))
        tf = txbox.text_frame
        tf.word_wrap = True
        self._populate_bullets(tf, bullets)

    def _populate_bullets(self, tf: TextFrame, bullets: list[BulletItem]) -> None:
        """Remplit un TextFrame avec des puces."""
        for idx, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()

            p.text = bullet.text
            p.level = bullet.level
            p.space_after = Pt(6)

            if p.runs:
                run = p.runs[0]
                run.font.size = Pt(18 - bullet.level * 2)
                run.font.bold = bullet.bold

    def _add_image_to_slide(
        self,
        slide: Slide,
        image_def: ImageDef,
        left_cm: float = 2.0,
        top_cm: float = 2.0,
        full_slide: bool = False,
    ) -> None:
        """Ajoute une image au slide.

        Args:
            slide: Slide cible.
            image_def: Definition de l'image.
            left_cm: Position gauche en cm.
            top_cm: Position haute en cm.
            full_slide: Si True, utilise des dimensions plus grandes.

        Raises:
            PresentationImageNotFoundError: Si l'image est introuvable.
        """
        image_path = self._resolve_image_path(image_def.filename)

        width = Cm(image_def.width_cm) if image_def.width_cm else None
        height = Cm(image_def.height_cm) if image_def.height_cm else None

        if not width and not height:
            width = Cm(20.0) if full_slide else Cm(10.0)

        slide.shapes.add_picture(str(image_path), Cm(left_cm), Cm(top_cm), width, height)

    def _resolve_image_path(self, filename: str) -> Path:
        """Resout le chemin d'une image avec securite.

        Args:
            filename: Nom du fichier image.

        Returns:
            Chemin absolu vers l'image.

        Raises:
            PresentationImageNotFoundError: Si l'image n'existe pas.
            PresentationGenerationError: Si path traversal detecte.
        """
        if ".." in filename or "/" in filename or "\\" in filename:
            raise PresentationGenerationError(
                message=f"Nom d'image invalide: {filename}",
                code="INVALID_IMAGE_NAME",
                suggestion="Le nom d'image ne doit pas contenir '..' , '/' ou '\\'.",
                parameter="image",
                retry=True,
            )

        image_path = self._images_path / filename
        resolved = image_path.resolve()
        if not resolved.is_relative_to(self._images_path.resolve()):
            raise PresentationGenerationError(
                message=f"Path traversal detecte: {filename}",
                code="PATH_TRAVERSAL",
                suggestion="Utiliser un nom de fichier simple sans chemin.",
                parameter="image",
                retry=True,
            )

        if not image_path.exists():
            available = self._list_available_images()
            raise PresentationImageNotFoundError(filename, available)

        return image_path

    def _list_available_images(self) -> list[str]:
        """Liste les images disponibles."""
        if not self._images_path.exists():
            return []
        extensions = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.svg")
        images: list[str] = []
        for ext in extensions:
            images.extend(f.name for f in self._images_path.glob(ext))
        return sorted(images)

    def _add_chart_to_slide(self, slide: Slide, chart_def: PresentationChartDef) -> None:
        """Ajoute un graphique au slide.

        Raises:
            PresentationChartError: En cas d'echec.
        """
        try:
            chart_type = _CHART_TYPE_MAP.get(chart_def.chart_type)
            if chart_type is None:
                msg = f"Type de graphique non supporte: {chart_def.chart_type}"
                raise PresentationGenerationError(msg)

            chart_data = CategoryChartData()
            chart_data.categories = chart_def.categories
            for series in chart_def.series:
                chart_data.add_series(series.name, series.values)

            chart_frame = slide.shapes.add_chart(
                chart_type,
                Cm(2.0),
                Cm(3.0),
                Cm(20.0),
                Cm(13.0),
                chart_data,
            )

            if chart_def.title:
                chart_frame.chart.has_title = True
                chart_frame.chart.chart_title.text_frame.text = chart_def.title

        except (PresentationChartError, PresentationGenerationError):
            raise
        except Exception as exc:
            raise PresentationChartError(
                chart_title=chart_def.title,
                reason=str(exc),
            ) from exc

    def _set_notes(self, slide: Slide, notes: str | None) -> None:
        """Definit les notes du presentateur sur un slide."""
        if not notes:
            return
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = notes

    # === File Management ===

    def save_and_verify(self, prs: Presentation, file_path: Path, filename: str) -> int:
        """Sauvegarde la presentation et verifie la taille.

        Returns:
            Taille du fichier en octets.

        Raises:
            PresentationOutputTooLargeError: Si le fichier depasse la taille max.
        """
        prs.save(str(file_path))
        file_size = file_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        if size_mb > self._max_output_size_mb:
            file_path.unlink()
            raise PresentationOutputTooLargeError(
                filename=filename,
                size_mb=size_mb,
                max_size_mb=self._max_output_size_mb,
            )
        return file_size

    def sanitize_filename(self, filename: str) -> str:
        """Securise le nom de fichier (path traversal prevention).

        Args:
            filename: Nom de fichier a securiser.

        Returns:
            Nom de fichier securise.

        Raises:
            PresentationGenerationError: Si le nom est invalide ou dangereux.
        """
        if ".." in filename or "/" in filename or "\\" in filename:
            raise PresentationGenerationError(
                message=f"Nom de fichier invalide: {filename}",
                code="INVALID_FILENAME",
                suggestion="Le nom de fichier ne doit pas contenir '..' , '/' ou '\\'.",
                parameter="filename",
                retry=True,
            )

        resolved = (self._output_path / filename).resolve()
        if not resolved.is_relative_to(self._output_path.resolve()):
            raise PresentationGenerationError(
                message=f"Path traversal detecte: {filename}",
                code="PATH_TRAVERSAL",
                suggestion="Utiliser un nom de fichier simple sans chemin.",
                parameter="filename",
                retry=True,
            )

        return filename

    def ensure_output_dir(self) -> None:
        """Cree le repertoire OUTPUT_PATH s'il n'existe pas."""
        self._output_path.mkdir(parents=True, exist_ok=True)
