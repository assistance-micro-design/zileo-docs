# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Models Pydantic pour la generation de documents Excel."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.models.types import CellValue


class CellStyleDef(BaseModel):
    """Definition de style pour une plage de cellules."""

    model_config = ConfigDict(extra="forbid")

    range: Annotated[str, Field(description="Plage de cellules. Ex: 'A1:D1'")]
    bold: bool = False
    italic: bool = False
    font_size: int | None = None
    font_color: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur de police en hex sans #. Ex: 'FF0000'",
        ),
    ]
    bg_color: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur de fond en hex sans #. Ex: '4472C4'",
        ),
    ]
    number_format: Annotated[
        str | None,
        Field(
            default=None,
            description="Format Excel. Ex: '#,##0.00', '0%', 'yyyy-mm-dd'",
        ),
    ]
    alignment: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^(left|center|right)$",
            description="Alignement horizontal",
        ),
    ]
    wrap_text: bool = False
    border: bool = False


class ChartDef(BaseModel):
    """Definition d'un graphique Excel."""

    model_config = ConfigDict(extra="forbid")

    type: Annotated[
        str,
        Field(
            pattern=r"^(bar|line|pie|scatter|area|column)$",
            description="Type de graphique",
        ),
    ]
    title: str | None = None
    data_range: Annotated[
        str,
        Field(description="Plage de donnees du graphique. Ex: 'B1:E5'"),
    ]
    categories_range: Annotated[
        str | None,
        Field(
            default=None,
            description="Plage des categories (axe X). Ex: 'A2:A5'",
        ),
    ]
    position: Annotated[
        str,
        Field(
            default="H2",
            description="Cellule ou placer le graphique. Ex: 'H2'",
        ),
    ]
    x_axis_title: str | None = None
    y_axis_title: str | None = None
    style: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            le=48,
            description="Numero de style openpyxl (1-48)",
        ),
    ]
    width: Annotated[float, Field(default=15.0, ge=5.0, le=40.0, description="Largeur en cm")]
    height: Annotated[float, Field(default=10.0, ge=5.0, le=30.0, description="Hauteur en cm")]


class DataValidationDef(BaseModel):
    """Definition d'une validation de donnees."""

    model_config = ConfigDict(extra="forbid")

    range: Annotated[str, Field(description="Plage de cellules. Ex: 'A2:A100'")]
    type: Annotated[
        str,
        Field(
            pattern=r"^(list|whole|decimal|date|textLength|custom)$",
            description="Type de validation",
        ),
    ]
    operator: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^(between|notBetween|equal|notEqual|greaterThan|lessThan|greaterThanOrEqual|lessThanOrEqual)$",
            description="Operateur de comparaison",
        ),
    ]
    formula1: str | None = None
    formula2: str | None = None
    values: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Raccourci pour type='list': liste des valeurs autorisees",
        ),
    ]
    error_message: str | None = None
    prompt_message: str | None = None


class MergedCellDef(BaseModel):
    """Definition d'une fusion de cellules."""

    model_config = ConfigDict(extra="forbid")

    range: Annotated[str, Field(description="Plage a fusionner. Ex: 'A1:D1'")]
    value: CellValue = None


class SheetDef(BaseModel):
    """Definition d'une feuille Excel."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=31, description="Nom de la feuille")]
    headers: Annotated[
        list[str] | None,
        Field(default=None, max_length=500, description="En-tetes de colonnes (max 500)"),
    ]
    rows: Annotated[
        list[Annotated[list[CellValue], Field(max_length=500)]],
        Field(
            default=[],
            max_length=10000,
            description="Lignes de donnees (max 10 000 lignes, max 500 colonnes)",
        ),
    ]
    column_widths: Annotated[
        dict[str, float] | None,
        Field(
            default=None,
            description="Largeurs de colonnes. Ex: {'A': 20, 'B': 15}",
        ),
    ]
    styles: list[CellStyleDef] = []
    charts: list[ChartDef] = []
    data_validations: list[DataValidationDef] = []
    merged_cells: list[MergedCellDef] = []
    auto_filter: bool = False
    freeze_panes: Annotated[
        str | None,
        Field(
            default=None,
            description="Cellule de gel. Ex: 'A2' pour geler la 1ere ligne",
        ),
    ]
    tab_color: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur de l'onglet en hex",
        ),
    ]
