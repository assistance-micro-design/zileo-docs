# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP pour la creation de documents Excel."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import CreateExcelParams
from src.services.excel.generator import ExcelGenerator


logger = logging.getLogger(__name__)


class CreateExcelTool(BaseMCPTool):
    """Cree un document Excel (.xlsx) avec donnees, styles, graphiques et validations.

    Herite de BaseMCPTool directement (pas besoin de Qdrant).
    Pattern sans DI, identique a IndexDocumentTool.
    """

    name: ClassVar[str] = "create_excel_document"
    description: ClassVar[str] = (
        "Create an Excel file (.xlsx) with structured data, formulas, styles, "
        "charts and data validation. "
        "Charts require 'type' field (bar|line|pie|scatter|area|column) and 'data_range'. "
        'Example: {"filename": "report.xlsx", "sheets": [{"name": "Data", '
        '"headers": ["Name", "Value"], "rows": [["A", 10]], '
        '"charts": [{"type": "bar", "data_range": "B1:B5", "title": "Chart"}]}]}. '
        "Returns: file path, sheet count and stats."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._generator = ExcelGenerator()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema et cree OUTPUT_PATH."""
        self._generator.ensure_output_dir()
        type(self).input_schema = CreateExcelParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la creation du fichier Excel.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de la creation (CreateExcelResult.model_dump()).
        """
        params = CreateExcelParams(**arguments)
        result = await self._generator.generate(params)
        return result.model_dump()
