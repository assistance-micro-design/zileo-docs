# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP pour inspecter la structure d'un fichier Excel genere."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar

from src.core.config import settings
from src.mcp.tools.base import BaseMCPTool
from src.models.api import InspectGeneratedFileParams
from src.services.inspection.file_inspector import FileInspector


logger = logging.getLogger(__name__)


class InspectGeneratedFileTool(BaseMCPTool):
    """Inspecte la structure d'un fichier Excel genere.

    Retourne la structure dans le format des tools d'edition
    pour permettre au LLM de construire directement ses operations.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.
    """

    name: ClassVar[str] = "inspect_generated_file"
    description: ClassVar[str] = (
        "Inspecte la structure d'un fichier Excel cree par create_excel_document. "
        "Retourne la structure dans le format du tool edit_excel_document "
        "pour permettre l'edition directe. "
        "Utiliser AVANT edit_excel_document pour voir le contenu actuel."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": (
                    "Nom du fichier a inspecter (.xlsx). "
                    "Doit exister dans OUTPUT_PATH. "
                    "Utiliser list_available_documents(source='generated') pour voir les fichiers disponibles."
                ),
            },
            "max_rows_per_sheet": {
                "type": "integer",
                "description": "Excel: nombre max de lignes a afficher par feuille (defaut: 10)",
                "default": 10,
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["filename"],
    }

    def __init__(self) -> None:
        """Initialise le tool."""
        super().__init__()
        self._output_path = Path(settings.OUTPUT_PATH)
        self._inspector = FileInspector(output_path=self._output_path)

    async def _do_initialize(self) -> None:
        """Pas d'initialisation requise pour ce tool."""

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Inspecte un fichier genere.

        Args:
            arguments: Parametres avec filename et optionnellement max_rows_per_sheet.

        Returns:
            Structure du fichier dans le vocabulaire des tools d'edition.
        """
        params = InspectGeneratedFileParams(**arguments)
        return await self._inspector.inspect(params.filename, params.max_rows_per_sheet)
