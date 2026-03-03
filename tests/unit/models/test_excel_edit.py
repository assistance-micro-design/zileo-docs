# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tests pour les models d'edition Excel."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.excel_edit import (
    AddChartOp,
    AddDataValidationOp,
    AddSheetOp,
    ApplyStylesOp,
    DeleteRowsOp,
    DeleteSheetOp,
    EditOp,
    InsertRowsOp,
    MergeCellsOp,
    RemoveChartsOp,
    RenameSheetOp,
    SetSheetPropertiesOp,
    UnmergeCellsOp,
    UpdateCellsOp,
)


class TestDiscriminatedUnion:
    """Tests du discriminated union EditOp."""

    def test_update_cells_discriminator(self) -> None:
        """UpdateCellsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "update_cells", "sheet": "S1", "cells": {"A1": 42}})
        assert isinstance(op, UpdateCellsOp)

    def test_insert_rows_discriminator(self) -> None:
        """InsertRowsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "insert_rows", "sheet": "S1", "rows": [["a", 1]]})
        assert isinstance(op, InsertRowsOp)

    def test_delete_rows_discriminator(self) -> None:
        """DeleteRowsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {"op": "delete_rows", "sheet": "S1", "start_row": 1, "end_row": 3}
        )
        assert isinstance(op, DeleteRowsOp)

    def test_add_sheet_discriminator(self) -> None:
        """AddSheetOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "add_sheet", "name": "New"})
        assert isinstance(op, AddSheetOp)

    def test_delete_sheet_discriminator(self) -> None:
        """DeleteSheetOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "delete_sheet", "name": "Old"})
        assert isinstance(op, DeleteSheetOp)

    def test_rename_sheet_discriminator(self) -> None:
        """RenameSheetOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "rename_sheet", "name": "Old", "new_name": "New"})
        assert isinstance(op, RenameSheetOp)

    def test_add_chart_discriminator(self) -> None:
        """AddChartOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {
                "op": "add_chart",
                "sheet": "S1",
                "chart": {"type": "bar", "data_range": "B1:B5", "position": "D1"},
            }
        )
        assert isinstance(op, AddChartOp)

    def test_remove_charts_discriminator(self) -> None:
        """RemoveChartsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "remove_charts", "sheet": "S1"})
        assert isinstance(op, RemoveChartsOp)

    def test_apply_styles_discriminator(self) -> None:
        """ApplyStylesOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {
                "op": "apply_styles",
                "sheet": "S1",
                "styles": [{"range": "A1", "bold": True}],
            }
        )
        assert isinstance(op, ApplyStylesOp)

    def test_add_data_validation_discriminator(self) -> None:
        """AddDataValidationOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {
                "op": "add_data_validation",
                "sheet": "S1",
                "validation": {"range": "A1:A10", "type": "list", "values": ["Oui", "Non"]},
            }
        )
        assert isinstance(op, AddDataValidationOp)

    def test_merge_cells_discriminator(self) -> None:
        """MergeCellsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {
                "op": "merge_cells",
                "sheet": "S1",
                "merge": {"range": "A1:C1", "value": "Title"},
            }
        )
        assert isinstance(op, MergeCellsOp)

    def test_unmerge_cells_discriminator(self) -> None:
        """UnmergeCellsOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python({"op": "unmerge_cells", "sheet": "S1", "range": "A1:C1"})
        assert isinstance(op, UnmergeCellsOp)

    def test_set_sheet_properties_discriminator(self) -> None:
        """SetSheetPropertiesOp reconnu par discriminator."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        op = adapter.validate_python(
            {
                "op": "set_sheet_properties",
                "sheet": "S1",
                "freeze_panes": "A2",
            }
        )
        assert isinstance(op, SetSheetPropertiesOp)

    def test_invalid_op_rejected(self) -> None:
        """Operation inconnue rejetee."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(EditOp)
        with pytest.raises(ValidationError):
            adapter.validate_python({"op": "invalid_op", "sheet": "S1"})


class TestOperationValidation:
    """Tests de validation des operations individuelles."""

    def test_update_cells_requires_cells(self) -> None:
        """UpdateCellsOp requiert cells non vide."""
        with pytest.raises(ValidationError):
            UpdateCellsOp(sheet="S1", cells={})

    def test_insert_rows_at_row_ge_1(self) -> None:
        """InsertRowsOp: at_row >= 1."""
        with pytest.raises(ValidationError):
            InsertRowsOp(sheet="S1", rows=[["a"]], at_row=0)

    def test_insert_rows_at_row_none_is_append(self) -> None:
        """InsertRowsOp: at_row=None signifie append."""
        op = InsertRowsOp(sheet="S1", rows=[["a"]])
        assert op.at_row is None

    def test_delete_rows_start_ge_1(self) -> None:
        """DeleteRowsOp: start_row >= 1."""
        with pytest.raises(ValidationError):
            DeleteRowsOp(sheet="S1", start_row=0, end_row=1)

    def test_add_sheet_name_max_31(self) -> None:
        """AddSheetOp: nom max 31 caracteres."""
        with pytest.raises(ValidationError):
            AddSheetOp(name="A" * 32)

    def test_add_sheet_name_min_1(self) -> None:
        """AddSheetOp: nom min 1 caractere."""
        with pytest.raises(ValidationError):
            AddSheetOp(name="")

    def test_rename_sheet_new_name_max_31(self) -> None:
        """RenameSheetOp: new_name max 31 caracteres."""
        with pytest.raises(ValidationError):
            RenameSheetOp(name="Old", new_name="A" * 32)

    def test_delete_rows_end_must_be_gte_start(self) -> None:
        """DeleteRowsOp: end_row doit etre >= start_row."""
        with pytest.raises(ValidationError, match="end_row"):
            DeleteRowsOp(sheet="S1", start_row=5, end_row=3)

    def test_delete_rows_same_start_end_valid(self) -> None:
        """DeleteRowsOp: start_row == end_row est valide (une seule ligne)."""
        op = DeleteRowsOp(sheet="S1", start_row=3, end_row=3)
        assert op.start_row == 3

    def test_insert_rows_requires_at_least_one_row(self) -> None:
        """InsertRowsOp: rows ne peut pas etre vide."""
        with pytest.raises(ValidationError):
            InsertRowsOp(sheet="S1", rows=[])

    def test_apply_styles_requires_at_least_one_style(self) -> None:
        """ApplyStylesOp: styles ne peut pas etre vide."""
        with pytest.raises(ValidationError):
            ApplyStylesOp(sheet="S1", styles=[])

    def test_set_sheet_properties_tab_color_hex(self) -> None:
        """SetSheetPropertiesOp: tab_color valide hex 6 chars."""
        with pytest.raises(ValidationError):
            SetSheetPropertiesOp(sheet="S1", tab_color="ZZZZZZ")

    def test_set_sheet_properties_valid_tab_color(self) -> None:
        """SetSheetPropertiesOp: tab_color hex valide."""
        op = SetSheetPropertiesOp(sheet="S1", tab_color="FF5733")
        assert op.tab_color == "FF5733"


class TestEditExcelParams:
    """Tests EditExcelParams et EditExcelResult dans api.py."""

    def test_valid_params(self) -> None:
        """Params valides avec une operation."""
        from src.models.api import EditExcelParams

        params = EditExcelParams(
            filename="test.xlsx",
            operations=[UpdateCellsOp(sheet="S1", cells={"A1": 42})],
        )
        assert params.filename == "test.xlsx"
        assert len(params.operations) == 1

    def test_filename_must_end_xlsx(self) -> None:
        """filename doit se terminer par .xlsx."""
        from src.models.api import EditExcelParams

        with pytest.raises(ValidationError, match="filename"):
            EditExcelParams(
                filename="test.csv",
                operations=[UpdateCellsOp(sheet="S1", cells={"A1": 1})],
            )

    def test_operations_min_1(self) -> None:
        """Au moins une operation requise."""
        from src.models.api import EditExcelParams

        with pytest.raises(ValidationError):
            EditExcelParams(filename="test.xlsx", operations=[])

    def test_result_model(self) -> None:
        """EditExcelResult se construit correctement."""
        from src.models.api import EditExcelResult

        result = EditExcelResult(
            file_path="/app/output/test.xlsx",
            filename="test.xlsx",
            operations_applied=3,
            operations_skipped=1,
            file_size_bytes=1024,
        )
        assert result.operations_applied == 3
        assert result.operations_skipped == 1
