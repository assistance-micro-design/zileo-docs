# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models Pydantic pour l'edition de presentations PowerPoint."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from src.models.presentation_generation import (
    BulletItem,
    ImageDef,
    PresentationChartDef,
    SlideDef,
    TextStyle,
)


class UpdateTitleOp(BaseModel):
    """Modifier le titre d'un slide."""

    op: Literal["update_title"] = "update_title"
    slide_index: Annotated[int, Field(ge=0, description="Index du slide (0-based)")]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    style: TextStyle | None = None


class UpdateSubtitleOp(BaseModel):
    """Modifier le sous-titre d'un slide."""

    op: Literal["update_subtitle"] = "update_subtitle"
    slide_index: Annotated[int, Field(ge=0)]
    subtitle: Annotated[str, Field(min_length=1, max_length=500)]


class UpdateBulletsOp(BaseModel):
    """Remplacer les puces d'un slide."""

    op: Literal["update_bullets"] = "update_bullets"
    slide_index: Annotated[int, Field(ge=0)]
    bullets: Annotated[list[BulletItem], Field(min_length=1, max_length=20)]


class AddSlideOp(BaseModel):
    """Ajouter un slide a la presentation."""

    op: Literal["add_slide"] = "add_slide"
    slide: SlideDef
    at_index: Annotated[
        int | None,
        Field(default=None, ge=0, description="Index d'insertion (None = append)"),
    ] = None


class DeleteSlideOp(BaseModel):
    """Supprimer un slide."""

    op: Literal["delete_slide"] = "delete_slide"
    slide_index: Annotated[int, Field(ge=0)]


class ReorderSlideOp(BaseModel):
    """Deplacer un slide vers une nouvelle position."""

    op: Literal["reorder_slide"] = "reorder_slide"
    from_index: Annotated[int, Field(ge=0)]
    to_index: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _validate_different_indices(self) -> ReorderSlideOp:
        """Empeche un reorder no-op (from == to) qui serait silencieusement ignore."""
        if self.from_index == self.to_index:
            msg = "from_index et to_index doivent etre differents"
            raise ValueError(msg)
        return self


class ReplaceImageOp(BaseModel):
    """Remplacer l'image d'un slide."""

    op: Literal["replace_image"] = "replace_image"
    slide_index: Annotated[int, Field(ge=0)]
    image: ImageDef


class AddImageOp(BaseModel):
    """Ajouter une image a un slide."""

    op: Literal["add_image"] = "add_image"
    slide_index: Annotated[int, Field(ge=0)]
    image: ImageDef


class UpdateNotesOp(BaseModel):
    """Modifier les notes du presentateur d'un slide."""

    op: Literal["update_notes"] = "update_notes"
    slide_index: Annotated[int, Field(ge=0)]
    notes: Annotated[str, Field(min_length=1, max_length=5000)]


class UpdateChartOp(BaseModel):
    """Remplacer le graphique d'un slide."""

    op: Literal["update_chart"] = "update_chart"
    slide_index: Annotated[int, Field(ge=0)]
    chart: PresentationChartDef


class SetBackgroundOp(BaseModel):
    """Definir la couleur de fond d'un slide."""

    op: Literal["set_background"] = "set_background"
    slide_index: Annotated[int, Field(ge=0)]
    color: Annotated[
        str,
        Field(
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur de fond en hex sans #. Ex: 'FFFFFF'",
        ),
    ]


# Discriminated union
PresentationEditOp = Annotated[
    UpdateTitleOp
    | UpdateSubtitleOp
    | UpdateBulletsOp
    | AddSlideOp
    | DeleteSlideOp
    | ReorderSlideOp
    | ReplaceImageOp
    | AddImageOp
    | UpdateNotesOp
    | UpdateChartOp
    | SetBackgroundOp,
    Field(discriminator="op"),
]
