# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models Pydantic pour l'edition de documents Excel."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from src.models.excel_generation import (
    CellStyleDef,
    ChartDef,
    DataValidationDef,
    MergedCellDef,
)
from src.models.types import CellValue


class UpdateCellsOp(BaseModel):
    """Modifier des valeurs de cellules."""

    op: Literal["update_cells"] = "update_cells"
    sheet: str
    cells: Annotated[
        dict[str, CellValue],
        Field(
            min_length=1,
            description="Map cellule -> valeur. Ex: {'A1': 42, 'B2': '=SUM(A1:A5)'}",
        ),
    ]


class InsertRowsOp(BaseModel):
    """Inserer des lignes."""

    op: Literal["insert_rows"] = "insert_rows"
    sheet: str
    rows: Annotated[list[Annotated[list[CellValue], Field(max_length=500)]], Field(min_length=1)]
    at_row: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            description="Inserer avant cette ligne (1-indexed). None = append",
        ),
    ]


class DeleteRowsOp(BaseModel):
    """Supprimer des lignes."""

    op: Literal["delete_rows"] = "delete_rows"
    sheet: str
    start_row: Annotated[int, Field(ge=1, description="Premiere ligne a supprimer (1-indexed).")]
    end_row: Annotated[
        int, Field(ge=1, description="Derniere ligne a supprimer (1-indexed, inclusive).")
    ]

    @model_validator(mode="after")
    def _validate_row_range(self) -> DeleteRowsOp:
        if self.end_row < self.start_row:
            msg = f"end_row ({self.end_row}) must be >= start_row ({self.start_row})"
            raise ValueError(msg)
        return self


class ApplyStylesOp(BaseModel):
    """Appliquer des styles a des cellules."""

    op: Literal["apply_styles"] = "apply_styles"
    sheet: str
    styles: Annotated[list[CellStyleDef], Field(min_length=1)]


class AddSheetOp(BaseModel):
    """Ajouter une feuille."""

    op: Literal["add_sheet"] = "add_sheet"
    name: Annotated[
        str, Field(min_length=1, max_length=31, description="Nom de la feuille (1-31 caracteres).")
    ]
    headers: Annotated[
        list[str] | None,
        Field(default=None, max_length=500, description="En-tetes (max 500)"),
    ]
    rows: list[Annotated[list[CellValue], Field(max_length=500)]] = []


class DeleteSheetOp(BaseModel):
    """Supprimer une feuille."""

    op: Literal["delete_sheet"] = "delete_sheet"
    name: str


class RenameSheetOp(BaseModel):
    """Renommer une feuille."""

    op: Literal["rename_sheet"] = "rename_sheet"
    name: str
    new_name: Annotated[
        str,
        Field(
            min_length=1, max_length=31, description="Nouveau nom de la feuille (1-31 caracteres)."
        ),
    ]


class AddChartOp(BaseModel):
    """Ajouter un graphique."""

    op: Literal["add_chart"] = "add_chart"
    sheet: str
    chart: ChartDef


class RemoveChartsOp(BaseModel):
    """Supprimer tous les graphiques d'une feuille."""

    op: Literal["remove_charts"] = "remove_charts"
    sheet: str


class AddDataValidationOp(BaseModel):
    """Ajouter une validation de donnees."""

    op: Literal["add_data_validation"] = "add_data_validation"
    sheet: str
    validation: DataValidationDef


class MergeCellsOp(BaseModel):
    """Fusionner des cellules."""

    op: Literal["merge_cells"] = "merge_cells"
    sheet: str
    merge: MergedCellDef


class UnmergeCellsOp(BaseModel):
    """Defusionner des cellules."""

    op: Literal["unmerge_cells"] = "unmerge_cells"
    sheet: str
    range: str


class SetSheetPropertiesOp(BaseModel):
    """Modifier les proprietes d'une feuille."""

    op: Literal["set_sheet_properties"] = "set_sheet_properties"
    sheet: str
    column_widths: dict[str, float] | None = None
    auto_filter: bool | None = None
    freeze_panes: str | None = None
    tab_color: Annotated[
        str | None,
        Field(
            default=None,
            pattern=r"^[0-9A-Fa-f]{6}$",
            description="Couleur d'onglet en hex 6 caracteres (ex: 'FF5733').",
        ),
    ]


# Discriminated union
EditOp = Annotated[
    UpdateCellsOp
    | InsertRowsOp
    | DeleteRowsOp
    | ApplyStylesOp
    | AddSheetOp
    | DeleteSheetOp
    | RenameSheetOp
    | AddChartOp
    | RemoveChartsOp
    | AddDataValidationOp
    | MergeCellsOp
    | UnmergeCellsOp
    | SetSheetPropertiesOp,
    Field(discriminator="op"),
]
