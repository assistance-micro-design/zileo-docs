# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour les models Pydantic de generation Excel."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.api import CreateExcelParams, CreateExcelResult
from src.models.excel_generation import (
    CellStyleDef,
    ChartDef,
    DataValidationDef,
    MergedCellDef,
    SheetDef,
)


class TestCellStyleDef:
    """Tests pour CellStyleDef."""

    def test_minimal_style(self) -> None:
        """Style minimal avec seulement la plage."""
        style = CellStyleDef(range="A1:D1")
        assert style.range == "A1:D1"
        assert style.bold is False
        assert style.italic is False
        assert style.font_size is None
        assert style.font_color is None
        assert style.bg_color is None
        assert style.number_format is None
        assert style.alignment is None
        assert style.wrap_text is False
        assert style.border is False

    def test_full_style(self) -> None:
        """Style complet avec toutes les options."""
        style = CellStyleDef(
            range="A1:E1",
            bold=True,
            italic=True,
            font_size=14,
            font_color="FF0000",
            bg_color="4472C4",
            number_format="#,##0.00",
            alignment="center",
            wrap_text=True,
            border=True,
        )
        assert style.bold is True
        assert style.font_color == "FF0000"
        assert style.bg_color == "4472C4"
        assert style.alignment == "center"

    def test_invalid_font_color(self) -> None:
        """Couleur de police invalide rejetee."""
        with pytest.raises(ValidationError, match="font_color"):
            CellStyleDef(range="A1", font_color="ZZZZZZ")

    def test_invalid_bg_color(self) -> None:
        """Couleur de fond invalide rejetee."""
        with pytest.raises(ValidationError, match="bg_color"):
            CellStyleDef(range="A1", bg_color="12345")  # 5 chars, not 6

    def test_invalid_alignment(self) -> None:
        """Alignement invalide rejete."""
        with pytest.raises(ValidationError, match="alignment"):
            CellStyleDef(range="A1", alignment="justify")


class TestChartDef:
    """Tests pour ChartDef."""

    def test_minimal_chart(self) -> None:
        """Graphique minimal."""
        chart = ChartDef(type="bar", data_range="B1:D3")
        assert chart.type == "bar"
        assert chart.data_range == "B1:D3"
        assert chart.position == "H2"
        assert chart.width == 15.0
        assert chart.height == 10.0

    def test_all_chart_types(self) -> None:
        """Tous les types de graphiques valides."""
        for chart_type in ("bar", "line", "pie", "scatter", "area", "column"):
            chart = ChartDef(type=chart_type, data_range="A1:B5")
            assert chart.type == chart_type

    def test_invalid_chart_type(self) -> None:
        """Type de graphique invalide rejete."""
        with pytest.raises(ValidationError, match="type"):
            ChartDef(type="radar", data_range="A1:B5")

    def test_chart_with_axes(self) -> None:
        """Graphique avec titres d'axes."""
        chart = ChartDef(
            type="line",
            data_range="B1:E5",
            categories_range="A2:A5",
            title="Ventes",
            x_axis_title="Mois",
            y_axis_title="Montant",
            position="G2",
        )
        assert chart.title == "Ventes"
        assert chart.x_axis_title == "Mois"

    def test_chart_style_bounds(self) -> None:
        """Style openpyxl entre 1 et 48."""
        chart = ChartDef(type="bar", data_range="A1:B5", style=10)
        assert chart.style == 10

        with pytest.raises(ValidationError):
            ChartDef(type="bar", data_range="A1:B5", style=0)

        with pytest.raises(ValidationError):
            ChartDef(type="bar", data_range="A1:B5", style=49)


class TestDataValidationDef:
    """Tests pour DataValidationDef."""

    def test_list_validation(self) -> None:
        """Validation de type liste."""
        dv = DataValidationDef(
            range="A2:A100",
            type="list",
            values=["Oui", "Non", "Peut-etre"],
        )
        assert dv.type == "list"
        assert dv.values == ["Oui", "Non", "Peut-etre"]

    def test_whole_number_validation(self) -> None:
        """Validation nombre entier."""
        dv = DataValidationDef(
            range="B2:B100",
            type="whole",
            operator="greaterThan",
            formula1="0",
        )
        assert dv.type == "whole"
        assert dv.operator == "greaterThan"

    def test_invalid_type(self) -> None:
        """Type de validation invalide rejete."""
        with pytest.raises(ValidationError, match="type"):
            DataValidationDef(range="A1", type="color")

    def test_invalid_operator(self) -> None:
        """Operateur invalide rejete."""
        with pytest.raises(ValidationError, match="operator"):
            DataValidationDef(range="A1", type="whole", operator="contains")


class TestMergedCellDef:
    """Tests pour MergedCellDef."""

    def test_merge_without_value(self) -> None:
        """Fusion sans valeur."""
        mc = MergedCellDef(range="A1:D1")
        assert mc.range == "A1:D1"
        assert mc.value is None

    def test_merge_with_string_value(self) -> None:
        """Fusion avec valeur string."""
        mc = MergedCellDef(range="A1:D1", value="Titre")
        assert mc.value == "Titre"

    def test_merge_with_numeric_value(self) -> None:
        """Fusion avec valeur numerique (CellValue)."""
        mc = MergedCellDef(range="A1:D1", value=42)
        assert mc.value == 42


class TestSheetDef:
    """Tests pour SheetDef."""

    def test_minimal_sheet(self) -> None:
        """Feuille minimale avec juste un nom."""
        sheet = SheetDef(name="Feuille1")
        assert sheet.name == "Feuille1"
        assert sheet.headers is None
        assert sheet.rows == []
        assert sheet.styles == []
        assert sheet.charts == []
        assert sheet.auto_filter is False
        assert sheet.freeze_panes is None

    def test_sheet_with_data(self) -> None:
        """Feuille avec headers et donnees."""
        sheet = SheetDef(
            name="Ventes",
            headers=["Produit", "Prix"],
            rows=[["Widget A", 100], ["Widget B", 200]],
        )
        assert sheet.headers == ["Produit", "Prix"]
        assert len(sheet.rows) == 2

    def test_sheet_name_too_long(self) -> None:
        """Nom de feuille > 31 caracteres rejete."""
        with pytest.raises(ValidationError, match="name"):
            SheetDef(name="A" * 32)

    def test_sheet_name_empty(self) -> None:
        """Nom de feuille vide rejete."""
        with pytest.raises(ValidationError, match="name"):
            SheetDef(name="")

    def test_sheet_with_datetime_cells(self) -> None:
        """CellValue accepte datetime."""
        now = datetime(2026, 1, 15, 10, 30)
        sheet = SheetDef(
            name="Dates",
            rows=[[now, "description"]],
        )
        assert sheet.rows[0][0] == now

    def test_sheet_with_formulas(self) -> None:
        """Les formules sont des strings commencant par =."""
        sheet = SheetDef(
            name="Calculs",
            rows=[["=SUM(A1:A10)", "=AVERAGE(B1:B10)"]],
        )
        assert sheet.rows[0][0] == "=SUM(A1:A10)"

    def test_sheet_tab_color(self) -> None:
        """Couleur d'onglet valide."""
        sheet = SheetDef(name="Test", tab_color="FF5733")
        assert sheet.tab_color == "FF5733"

    def test_sheet_invalid_tab_color(self) -> None:
        """Couleur d'onglet invalide rejetee."""
        with pytest.raises(ValidationError, match="tab_color"):
            SheetDef(name="Test", tab_color="GGGGGG")

    def test_row_max_500_columns(self) -> None:
        """Une ligne avec 500 colonnes est acceptee."""
        sheet = SheetDef(name="Wide", rows=[list(range(500))])
        assert len(sheet.rows[0]) == 500

    def test_row_over_500_columns_rejected(self) -> None:
        """Une ligne avec > 500 colonnes est rejetee."""
        with pytest.raises(ValidationError):
            SheetDef(name="TooWide", rows=[list(range(501))])

    def test_headers_max_500(self) -> None:
        """500 headers sont acceptes."""
        headers = [f"H{i}" for i in range(500)]
        sheet = SheetDef(name="Wide", headers=headers)
        assert len(sheet.headers) == 500  # type: ignore[arg-type]

    def test_headers_over_500_rejected(self) -> None:
        """Plus de 500 headers sont rejetes."""
        headers = [f"H{i}" for i in range(501)]
        with pytest.raises(ValidationError):
            SheetDef(name="TooWide", headers=headers)


class TestCreateExcelParams:
    """Tests pour CreateExcelParams."""

    def test_minimal_params(self) -> None:
        """Params minimaux valides."""
        params = CreateExcelParams(
            filename="test.xlsx",
            sheets=[SheetDef(name="Feuille1")],
        )
        assert params.filename == "test.xlsx"
        assert len(params.sheets) == 1
        assert params.author is None

    def test_filename_must_end_xlsx(self) -> None:
        """Filename doit se terminer par .xlsx."""
        with pytest.raises(ValidationError, match="filename"):
            CreateExcelParams(
                filename="test.csv",
                sheets=[SheetDef(name="F1")],
            )

    def test_filename_with_spaces_and_parens(self) -> None:
        """Filename avec espaces et parentheses autorise."""
        params = CreateExcelParams(
            filename="rapport ventes (Q1).xlsx",
            sheets=[SheetDef(name="F1")],
        )
        assert params.filename == "rapport ventes (Q1).xlsx"

    def test_filename_path_traversal_rejected(self) -> None:
        """Filename avec path traversal rejete par regex."""
        with pytest.raises(ValidationError, match="filename"):
            CreateExcelParams(
                filename="../evil.xlsx",
                sheets=[SheetDef(name="F1")],
            )

    def test_filename_with_slash_rejected(self) -> None:
        """Filename avec slash rejete."""
        with pytest.raises(ValidationError, match="filename"):
            CreateExcelParams(
                filename="sub/file.xlsx",
                sheets=[SheetDef(name="F1")],
            )

    def test_sheets_empty_rejected(self) -> None:
        """Liste de feuilles vide rejetee."""
        with pytest.raises(ValidationError, match="sheets"):
            CreateExcelParams(filename="test.xlsx", sheets=[])

    def test_with_author(self) -> None:
        """Params avec auteur."""
        params = CreateExcelParams(
            filename="test.xlsx",
            sheets=[SheetDef(name="F1")],
            author="Zileo Docs",
        )
        assert params.author == "Zileo Docs"

    def test_author_max_length_255(self) -> None:
        """Author respecte max_length=255."""
        # 255 caracteres: OK
        params = CreateExcelParams(
            filename="test.xlsx",
            sheets=[SheetDef(name="F1")],
            author="A" * 255,
        )
        assert len(params.author) == 255  # type: ignore[arg-type]

    def test_author_too_long_rejected(self) -> None:
        """Author > 255 caracteres rejete."""
        with pytest.raises(ValidationError, match="author"):
            CreateExcelParams(
                filename="test.xlsx",
                sheets=[SheetDef(name="F1")],
                author="A" * 256,
            )


class TestCreateExcelResult:
    """Tests pour CreateExcelResult."""

    def test_result_fields(self) -> None:
        """Tous les champs du resultat."""
        result = CreateExcelResult(
            file_path="/app/output/test.xlsx",
            filename="test.xlsx",
            sheets_created=2,
            total_rows=50,
            total_charts=1,
            file_size_bytes=8432,
            overwritten=False,
        )
        assert result.file_path == "/app/output/test.xlsx"
        assert result.sheets_created == 2
        assert result.total_rows == 50
        assert result.total_charts == 1
        assert result.file_size_bytes == 8432
        assert result.overwritten is False

    def test_overwritten_default_false(self) -> None:
        """Overwritten defaut a False."""
        result = CreateExcelResult(
            file_path="/app/output/test.xlsx",
            filename="test.xlsx",
            sheets_created=1,
            total_rows=0,
            total_charts=0,
            file_size_bytes=1000,
        )
        assert result.overwritten is False
