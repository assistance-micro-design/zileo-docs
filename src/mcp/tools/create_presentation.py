# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour la creation de presentations PowerPoint."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import CreatePresentationParams
from src.services.presentation.generator import PresentationGenerator


logger = logging.getLogger(__name__)


class CreatePresentationTool(BaseMCPTool):
    """Cree une presentation PowerPoint (.pptx) avec slides, texte, images et graphiques.

    Herite de BaseMCPTool directement (pas besoin de Qdrant).
    Pattern sans DI, identique a CreateExcelTool.
    """

    name: ClassVar[str] = "create_presentation"
    description: ClassVar[str] = (
        "Create a PowerPoint presentation (.pptx) with slides, text, images and charts. "
        "8 layout types: title_slide, content_bullets, content_with_image, section_header, "
        "two_columns, image_full, chart_slide, closing. "
        'Example: {"filename": "report.pptx", "slides": [{"layout": "title_slide", '
        '"title": "My Presentation", "subtitle": "By team"}]}. '
        "Returns: file path, slide count and stats."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        """Initialise le tool et instancie le generateur PowerPoint."""
        super().__init__()
        self._generator = PresentationGenerator()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema et cree OUTPUT_PATH."""
        self._generator.ensure_output_dir()
        type(self).input_schema = CreatePresentationParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la creation de la presentation.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de la creation (CreatePresentationResult.model_dump()).
        """
        params = CreatePresentationParams(**arguments)
        result = await self._generator.generate(params)
        return result.model_dump()
