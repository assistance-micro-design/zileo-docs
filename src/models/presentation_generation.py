# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models Pydantic pour la generation de presentations PowerPoint."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SlideLayout(str, Enum):
    """Types de layout de slide disponibles."""

    TITLE_SLIDE = "title_slide"
    CONTENT_BULLETS = "content_bullets"
    CONTENT_WITH_IMAGE = "content_with_image"
    SECTION_HEADER = "section_header"
    TWO_COLUMNS = "two_columns"
    IMAGE_FULL = "image_full"
    CHART_SLIDE = "chart_slide"
    CLOSING = "closing"


class TextStyle(BaseModel):
    """Style de texte pour un titre ou un element."""

    bold: bool = False
    italic: bool = False
    font_size: Annotated[int | None, Field(default=None, ge=8, le=96)] = None
    font_color: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur de police en hex sans #. Ex: 'FF0000'",
        ),
    ] = None


class BulletItem(BaseModel):
    """Element de liste a puces."""

    text: Annotated[str, Field(min_length=1, max_length=500)]
    level: Annotated[int, Field(default=0, ge=0, le=3, description="Niveau d'indentation (0-3)")]
    bold: bool = False


class ImageDef(BaseModel):
    """Definition d'une image pour un slide."""

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            description="Nom du fichier image dans le dossier images PowerPoint",
        ),
    ]
    width_cm: Annotated[float | None, Field(default=None, ge=1.0, le=33.87)] = None
    height_cm: Annotated[float | None, Field(default=None, ge=1.0, le=19.05)] = None


class ChartSeriesDef(BaseModel):
    """Definition d'une serie de donnees pour un graphique."""

    name: Annotated[str, Field(min_length=1, max_length=100)]
    values: Annotated[
        list[int | float],
        Field(min_length=1, max_length=50),
    ]


class PresentationChartDef(BaseModel):
    """Definition d'un graphique pour un slide."""

    chart_type: Annotated[
        str,
        Field(
            pattern=r"^(bar|line|pie|scatter|area|column|doughnut)$",
            description="Type de graphique",
        ),
    ]
    title: str | None = None
    categories: Annotated[
        list[str],
        Field(min_length=1, max_length=50, description="Labels des categories (axe X)"),
    ]
    series: Annotated[
        list[ChartSeriesDef],
        Field(min_length=1, max_length=10, description="Series de donnees"),
    ]


# === Slide Definitions (Discriminated Union) ===


class TitleSlideDef(BaseModel):
    """Slide de titre (page de garde)."""

    layout: Literal["title_slide"] = "title_slide"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    subtitle: str | None = None
    title_style: TextStyle | None = None
    notes: str | None = None


class ContentBulletsSlideDef(BaseModel):
    """Slide avec liste a puces."""

    layout: Literal["content_bullets"] = "content_bullets"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    bullets: Annotated[list[BulletItem], Field(min_length=1, max_length=20)]
    title_style: TextStyle | None = None
    notes: str | None = None


class ContentWithImageSlideDef(BaseModel):
    """Slide avec texte et image."""

    layout: Literal["content_with_image"] = "content_with_image"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    bullets: Annotated[list[BulletItem], Field(min_length=1, max_length=10)]
    image: ImageDef
    title_style: TextStyle | None = None
    notes: str | None = None


class SectionHeaderSlideDef(BaseModel):
    """Slide de transition entre sections."""

    layout: Literal["section_header"] = "section_header"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    subtitle: str | None = None
    title_style: TextStyle | None = None
    notes: str | None = None


class TwoColumnsSlideDef(BaseModel):
    """Slide a deux colonnes."""

    layout: Literal["two_columns"] = "two_columns"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    left_bullets: Annotated[list[BulletItem], Field(min_length=1, max_length=10)]
    right_bullets: Annotated[list[BulletItem], Field(min_length=1, max_length=10)]
    title_style: TextStyle | None = None
    notes: str | None = None


class ImageFullSlideDef(BaseModel):
    """Slide image pleine page."""

    layout: Literal["image_full"] = "image_full"
    image: ImageDef
    title: str | None = None
    caption: str | None = None
    title_style: TextStyle | None = None
    notes: str | None = None


class ChartSlideDef(BaseModel):
    """Slide avec graphique."""

    layout: Literal["chart_slide"] = "chart_slide"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    chart: PresentationChartDef
    title_style: TextStyle | None = None
    notes: str | None = None


class ClosingSlideDef(BaseModel):
    """Slide de cloture (Q&A, merci, etc.)."""

    layout: Literal["closing"] = "closing"
    title: Annotated[str, Field(min_length=1, max_length=200)]
    subtitle: str | None = None
    bullets: list[BulletItem] | None = None
    title_style: TextStyle | None = None
    notes: str | None = None


# Discriminated union for all slide types
SlideDef = Annotated[
    TitleSlideDef
    | ContentBulletsSlideDef
    | ContentWithImageSlideDef
    | SectionHeaderSlideDef
    | TwoColumnsSlideDef
    | ImageFullSlideDef
    | ChartSlideDef
    | ClosingSlideDef,
    Field(discriminator="layout"),
]
