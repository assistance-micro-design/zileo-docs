# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour l'edition de presentations PowerPoint existantes."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import EditPresentationParams
from src.services.presentation.editor import PresentationEditor


logger = logging.getLogger(__name__)


class EditPresentationTool(BaseMCPTool):
    """Edite une presentation PowerPoint (.pptx) existante dans OUTPUT_PATH.

    Supporte: modification de titres/sous-titres/puces, ajout/suppression/reordonnancement
    de slides, gestion d'images et graphiques, notes du presentateur, couleur de fond.

    Herite de BaseMCPTool directement (pas besoin de Qdrant).
    Pattern sans DI, identique a EditExcelTool.
    """

    name: ClassVar[str] = "edit_presentation"
    description: ClassVar[str] = (
        "Edit an existing PowerPoint file (.pptx). "
        "Requires: file created by create_presentation. "
        "Each operation MUST have an 'op' field. "
        "Available ops: update_title, update_subtitle, update_bullets, add_slide, "
        "delete_slide, reorder_slide, replace_image, add_image, update_notes, "
        "update_chart, set_background. "
        'Example: {"filename": "report.pptx", "operations": ['
        '{"op": "update_title", "slide_index": 0, "title": "New Title"}, '
        '{"op": "add_slide", "slide": {"layout": "content_bullets", '
        '"title": "New", "bullets": [{"text": "Point"}]}}]}. '
        "Returns: operation count and file stats."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        """Initialise le tool avec une instance PresentationEditor."""
        super().__init__()
        self._editor = PresentationEditor()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema et cree OUTPUT_PATH."""
        self._editor._generator.ensure_output_dir()
        type(self).input_schema = EditPresentationParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'edition de la presentation.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de l'edition (EditPresentationResult.model_dump()).
        """
        params = EditPresentationParams(**arguments)
        result = await self._editor.edit(params)
        return result.model_dump()
