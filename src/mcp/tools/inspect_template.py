# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour inspecter la structure d'un template PowerPoint."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import InspectTemplateParams
from src.services.inspection.template_inspector import TemplateInspector


logger = logging.getLogger(__name__)


class InspectTemplateTool(BaseMCPTool):
    """Inspecte un template PowerPoint pour lister ses layouts et placeholders.

    Retourne la structure du template (layouts, placeholders, theme, dimensions)
    pour permettre au LLM de comprendre comment le template est organise.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.
    """

    name: ClassVar[str] = "inspect_template"
    description: ClassVar[str] = (
        "Inspect a PowerPoint template (.pptx) to list its slide layouts, "
        "placeholders, theme and dimensions. "
        "Use before create_presentation to understand template structure. "
        "Returns: layouts with placeholders (index, name, type, position), "
        "theme info, slide dimensions."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        """Initialise le tool et instancie le TemplateInspector."""
        super().__init__()
        self._inspector = TemplateInspector()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema."""
        type(self).input_schema = InspectTemplateParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute l'inspection du template.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de l'inspection.
        """
        params = InspectTemplateParams(**arguments)
        return await self._inspector.inspect(params.template)
