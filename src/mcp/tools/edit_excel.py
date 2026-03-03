# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour l'edition de documents Excel existants."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import EditExcelParams
from src.services.excel.editor import ExcelEditor


logger = logging.getLogger(__name__)


class EditExcelTool(BaseMCPTool):
    """Edite un document Excel (.xlsx) existant dans OUTPUT_PATH.

    Supporte: modification de cellules, insertion/suppression de lignes,
    ajout/suppression de feuilles et graphiques, styles, validations, fusions.

    Herite de BaseMCPTool directement (pas besoin de Qdrant).
    Pattern sans DI, identique a CreateExcelTool.
    """

    name: ClassVar[str] = "edit_excel_document"
    description: ClassVar[str] = (
        "Edit an existing Excel file (.xlsx). "
        "Requires: file created by create_excel_document. "
        "Each operation MUST have an 'op' field. "
        "Available ops: update_cells, insert_rows, delete_rows, apply_styles, "
        "add_sheet, delete_sheet, rename_sheet, add_chart, remove_charts, "
        "add_data_validation, merge_cells, unmerge_cells, set_sheet_properties. "
        'Example: {"filename": "report.xlsx", "operations": ['
        '{"op": "update_cells", "sheet": "Sheet1", "cells": {"A1": 42}}, '
        '{"op": "add_chart", "sheet": "Sheet1", "chart": {"type": "bar", "data_range": "A1:B5", "title": "Sales"}}]}. '
        "Returns: operation count and file stats."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        """Initialise le tool avec une instance ExcelEditor."""
        super().__init__()
        self._editor = ExcelEditor()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema et cree OUTPUT_PATH."""
        self._editor._generator.ensure_output_dir()
        type(self).input_schema = EditExcelParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'edition du fichier Excel.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de l'edition (EditExcelResult.model_dump()).
        """
        params = EditExcelParams(**arguments)
        result = await self._editor.edit(params)
        return result.model_dump()
