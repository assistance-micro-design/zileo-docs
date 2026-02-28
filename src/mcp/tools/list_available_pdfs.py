# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour lister les fichiers PDF disponibles dans le dossier.

Deprecated: Utiliser list_available_documents avec type_filter='pdf'.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.mcp.tools.list_available_documents import ListAvailableDocumentsTool


logger = logging.getLogger(__name__)


class ListAvailablePdfsTool(BaseMCPTool):
    """Tool MCP pour lister les fichiers PDF disponibles.

    Deprecated: Delegue a ListAvailableDocumentsTool avec type_filter='pdf'.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = ListAvailablePdfsTool()
        >>> result = await tool.execute({})
        >>> for pdf in result["files"]:
        ...     print(f"{pdf['filename']}: {pdf['path']}")
    """

    name: ClassVar[str] = "list_available_pdfs"
    description: ClassVar[str] = (
        "Liste les fichiers PDF disponibles dans le dossier monte. "
        "Utiliser pour savoir quels PDFs peuvent etre indexes. "
        "Retourne: liste des fichiers avec chemin, taille, date."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "subdirectory": {
                "type": "string",
                "description": "Sous-dossier optionnel a scanner (relatif au dossier racine)",
                "default": "",
            },
            "recursive": {
                "type": "boolean",
                "description": "Scanner recursivement les sous-dossiers (defaut: true)",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(self) -> None:
        """Initialise le tool."""
        super().__init__()
        self._delegate = ListAvailableDocumentsTool()

    async def _do_initialize(self) -> None:
        """Initialise le tool delegue."""
        await self._delegate.initialize()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Liste les fichiers PDF via delegation a list_available_documents.

        Args:
            arguments: Parametres optionnels:
                - subdirectory: Sous-dossier a scanner
                - recursive: Scanner recursivement

        Returns:
            Dictionnaire avec:
                - base_path: Chemin du dossier scanne
                - total_files: Nombre de fichiers PDF
                - files: Liste des fichiers avec:
                    - filename: Nom du fichier
                    - path: Chemin absolu (pour index_document)
                    - size_mb: Taille en MB
                    - modified_at: Date de modification
        """
        warnings.warn(
            "list_available_pdfs is deprecated. "
            "Use list_available_documents with type_filter='pdf'.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Deleguer avec type_filter='pdf'
        delegate_args = {
            "type_filter": "pdf",
            "subdirectory": arguments.get("subdirectory", ""),
            "recursive": arguments.get("recursive", True),
        }

        return await self._delegate.execute(delegate_args)
