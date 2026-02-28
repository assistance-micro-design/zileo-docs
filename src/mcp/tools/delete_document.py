# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour supprimer un document de l'index vectoriel."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import VectorStoreMCPTool
from src.models.api import DeleteDocumentParams


logger = logging.getLogger(__name__)


class DeleteDocumentTool(VectorStoreMCPTool):
    """Tool MCP pour supprimer un document de l'index vectoriel.

    Ce tool supprime uniquement les donnees du document dans Qdrant.
    Le fichier PDF source n'est PAS supprime du systeme de fichiers.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = DeleteDocumentTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({"document_id": "doc-abc123"})
        >>> print(f"Supprime: {result['chunks_deleted']} chunks")
    """

    name: ClassVar[str] = "delete_document"
    description: ClassVar[str] = (
        "Supprime un document de l'index vectoriel (Qdrant). "
        "Ne supprime PAS le fichier PDF source. "
        "Retourne: nombre de chunks supprimes, statut."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "ID du document a supprimer (retourne par index_document). Ex: 'doc-abc123'",
            },
        },
        "required": ["document_id"],
    }

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Supprime un document de l'index vectoriel.

        Args:
            arguments: Parametres:
                - document_id: ID du document a supprimer

        Returns:
            Dictionnaire avec:
                - document_id: ID du document
                - chunks_deleted: Nombre de chunks supprimes
                - status: "deleted" si supprime, "not_found" si inexistant
        """
        # Valider les parametres
        params = DeleteDocumentParams(**arguments)

        logger.info("Suppression document: %s", params.document_id)

        # Supprimer les chunks du document
        chunks_deleted = await self._vector_store.delete_document(params.document_id)

        status = "deleted" if chunks_deleted > 0 else "not_found"

        logger.info(
            "Document %s: %d chunks supprimes (status=%s)",
            params.document_id,
            chunks_deleted,
            status,
        )

        return {
            "document_id": params.document_id,
            "chunks_deleted": chunks_deleted,
            "status": status,
        }
