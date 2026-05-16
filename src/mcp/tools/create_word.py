# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP pour la creation de documents Word."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.models.api import CreateWordParams
from src.services.word.generator import WordGenerator


logger = logging.getLogger(__name__)


class CreateWordTool(BaseMCPTool):
    """Cree un document Word (.docx) a partir de contenu Markdown.

    Herite de BaseMCPTool directement (pas besoin de Qdrant).
    """

    name: ClassVar[str] = "create_word_document"
    description: ClassVar[str] = (
        "Create a Word file (.docx) from Markdown content. "
        "Supports headings, bold, italic, bullet/numbered lists (nested), "
        "tables, code blocks, blockquotes and page breaks (---). "
        'Example: {"filename": "report.docx", "content": "# Title\\n\\nHello **world**"}. '
        "Returns: file path and size."
    )
    input_schema: ClassVar[dict[str, Any]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._generator = WordGenerator()

    async def _do_initialize(self) -> None:
        """Initialise le tool: genere input_schema et cree OUTPUT_PATH."""
        self._generator.ensure_output_dir()
        type(self).input_schema = CreateWordParams.model_json_schema()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la creation du fichier Word.

        Args:
            arguments: Parametres du tool (valides via Pydantic).

        Returns:
            Resultat de la creation (CreateWordResult.model_dump()).
        """
        params = CreateWordParams(**arguments)
        result = await self._generator.generate(params)
        return result.model_dump()
