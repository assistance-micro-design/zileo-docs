# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Modèles Pydantic pour l'extraction Excel."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.models.types import CellValue, FormulaResult


class CellType(str, Enum):
    """Type de données d'une cellule Excel."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    FORMULA = "formula"
    EMPTY = "empty"
    ERROR = "error"


class ExcelCell(BaseModel):
    """Cellule Excel avec valeur et formule optionnelle."""

    row: int = Field(..., ge=1, description="Numéro de ligne (1-indexed)")
    column: int = Field(..., ge=1, description="Numéro de colonne (1-indexed)")
    column_letter: str = Field(..., description="Lettre de colonne (A, B, C...)")
    value: CellValue = Field(None, description="Valeur calculée de la cellule")
    formula: str | None = Field(None, description="Formule brute si présente")
    cell_type: CellType = Field(..., description="Type de données")

    def to_dict(self) -> dict[str, str | None]:
        """Convertit en dictionnaire pour stockage."""
        return {
            "cell": f"{self.column_letter}{self.row}",
            "value": str(self.value) if self.value is not None else None,
            "formula": self.formula,
            "type": self.cell_type.value,
        }


class ExcelFormula(BaseModel):
    """Formule Excel avec contexte."""

    cell: str = Field(..., description="Référence cellule (ex: C10)")
    sheet: str = Field(..., description="Nom de la feuille")
    formula: str = Field(..., description="Formule brute (ex: =SUM(A1:A10))")
    result: FormulaResult = Field(None, description="Résultat calculé")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Cellules référencées par la formule",
    )


class ExcelTable(BaseModel):
    """Tableau détecté dans une feuille Excel."""

    name: str | None = Field(None, description="Nom du tableau si défini")
    range: str = Field(..., description="Plage du tableau (ex: A1:D10)")
    headers: list[str] = Field(default_factory=list, description="En-têtes de colonnes")
    data: list[list[CellValue]] = Field(
        default_factory=list,
        description="Données ligne par ligne",
    )

    def to_markdown(self) -> str:
        """Convertit le tableau en Markdown."""
        if not self.headers and not self.data:
            return ""

        lines: list[str] = []

        # En-têtes
        if self.headers:
            lines.append("| " + " | ".join(str(h) for h in self.headers) + " |")
            lines.append("| " + " | ".join("---" for _ in self.headers) + " |")

        # Données
        for row in self.data:
            cells = [str(cell) if cell is not None else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)


class ExcelSheet(BaseModel):
    """Feuille Excel avec données structurées."""

    name: str = Field(..., description="Nom de la feuille")
    index: int = Field(..., ge=0, description="Index de la feuille (0-indexed)")
    rows_count: int = Field(..., ge=0, description="Nombre de lignes avec données")
    columns_count: int = Field(..., ge=0, description="Nombre de colonnes avec données")

    # Données
    cells: list[list[ExcelCell]] = Field(
        default_factory=list,
        description="Grille de cellules (lignes x colonnes)",
    )
    tables: list[ExcelTable] = Field(
        default_factory=list,
        description="Tableaux détectés",
    )

    # Formules
    formulas: list[ExcelFormula] = Field(
        default_factory=list,
        description="Toutes les formules de la feuille",
    )

    # Structure
    merged_cells: list[str] = Field(
        default_factory=list,
        description="Plages de cellules fusionnées (ex: A1:B2)",
    )

    def get_text_content(self) -> str:
        """Génère le contenu textuel pour embedding."""
        lines: list[str] = [f"## Feuille: {self.name}\n"]

        # Tableaux officiels Excel en Markdown
        for table in self.tables:
            if table.name:
                lines.append(f"### Tableau: {table.name}\n")
            lines.append(table.to_markdown())
            lines.append("")

        # Si pas de tableaux officiels, générer un tableau à partir des cellules
        if not self.tables and self.cells:
            lines.append(self._cells_to_markdown())
            lines.append("")

        # Formules
        if self.formulas:
            lines.append("### Formules\n")
            for f in self.formulas:
                lines.append(f"- `{f.cell}`: `{f.formula}` = {f.result}")
            lines.append("")

        return "\n".join(lines)

    def _cells_to_markdown(self) -> str:
        """Convertit les cellules en tableau Markdown."""
        if not self.cells:
            return ""

        lines: list[str] = []
        header_added = False

        for row in self.cells:
            # Extraire les valeurs de la ligne
            values = []
            for cell in row:
                values.append(str(cell.value).replace("|", "\\|") if cell.value is not None else "")

            # Ignorer les lignes entièrement vides
            if not any(v.strip() for v in values):
                continue

            lines.append("| " + " | ".join(values) + " |")

            # Ajouter le séparateur après la première ligne non-vide (en-têtes)
            if not header_added:
                lines.append("| " + " | ".join("---" for _ in values) + " |")
                header_added = True

        return "\n".join(lines)


class ExcelDocument(BaseModel):
    """Document Excel complet."""

    filename: str = Field(..., description="Nom du fichier")
    file_path: str = Field(..., description="Chemin complet du fichier")
    format: str = Field(..., description="Format: xlsx ou xls")

    sheets: list[ExcelSheet] = Field(
        default_factory=list,
        description="Feuilles du classeur",
    )

    # Métadonnées globales
    named_ranges: dict[str, str] = Field(
        default_factory=dict,
        description="Plages nommées (Nom -> Plage)",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Propriétés du document (auteur, titre, etc.)",
    )

    # Statistiques
    total_formulas: int = Field(0, description="Nombre total de formules")
    total_tables: int = Field(0, description="Nombre total de tableaux")

    def get_all_formulas(self) -> list[ExcelFormula]:
        """Récupère toutes les formules du classeur."""
        formulas: list[ExcelFormula] = []
        for sheet in self.sheets:
            formulas.extend(sheet.formulas)
        return formulas

    def to_markdown(self) -> str:
        """Génère le contenu Markdown complet."""
        lines: list[str] = [f"# {self.filename}\n"]

        for sheet in self.sheets:
            lines.append(sheet.get_text_content())

        return "\n".join(lines)
