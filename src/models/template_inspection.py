# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models Pydantic pour l'inspection de templates PowerPoint."""

from __future__ import annotations

from pydantic import BaseModel


class PlaceholderInfo(BaseModel):
    """Informations sur un placeholder de layout.

    Attributes:
        idx: Index du placeholder dans le layout.
        name: Nom du placeholder (ex: "Title 1").
        type: Type du placeholder (TITLE, SUBTITLE, BODY, PICTURE, etc.).
        left_cm: Position gauche en cm.
        top_cm: Position haute en cm.
        width_cm: Largeur en cm.
        height_cm: Hauteur en cm.
    """

    idx: int
    name: str
    type: str
    left_cm: float
    top_cm: float
    width_cm: float
    height_cm: float


class LayoutInfo(BaseModel):
    """Informations sur un slide layout.

    Attributes:
        index: Index du layout dans la collection.
        name: Nom du layout (ex: "Title Slide", "Blank").
        placeholders: Liste des placeholders du layout.
    """

    index: int
    name: str
    placeholders: list[PlaceholderInfo]


class ThemeInfo(BaseModel):
    """Informations sur le theme du template.

    Attributes:
        name: Nom du theme.
        color_scheme: Nom du color scheme.
        font_major: Police majeure (titres).
        font_minor: Police mineure (corps).
    """

    name: str | None = None
    color_scheme: str | None = None
    font_major: str | None = None
    font_minor: str | None = None


class TemplateInspectionResult(BaseModel):
    """Resultat de l'inspection d'un template PowerPoint.

    Attributes:
        template: Nom du fichier template.
        file_size_bytes: Taille du fichier en octets.
        slide_width_cm: Largeur du slide en cm.
        slide_height_cm: Hauteur du slide en cm.
        theme: Informations sur le theme.
        total_layouts: Nombre total de layouts.
        layouts: Liste des layouts avec leurs placeholders.
        existing_slides_count: Nombre de slides existants dans le template.
        hint: Message explicatif pour le LLM.
    """

    template: str
    file_size_bytes: int
    slide_width_cm: float
    slide_height_cm: float
    theme: ThemeInfo
    total_layouts: int
    layouts: list[LayoutInfo]
    existing_slides_count: int
    hint: str
