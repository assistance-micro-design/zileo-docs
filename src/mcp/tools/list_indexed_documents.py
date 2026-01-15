"""Tool MCP pour lister les documents indexes dans Qdrant."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.base import BaseMCPTool
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class ListIndexedDocumentsTool(BaseMCPTool):
    """Tool MCP pour lister tous les documents indexes dans Qdrant.

    Ce tool permet au LLM de decouvrir les documents disponibles
    pour la recherche ou la suppression.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = ListIndexedDocumentsTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({})
        >>> for doc in result["documents"]:
        ...     print(f"{doc['filename']}: {doc['document_id']}")
    """

    name: ClassVar[str] = "list_indexed_documents"
    description: ClassVar[str] = (
        "Liste tous les documents deja indexes dans Qdrant. "
        "Utiliser pour connaitre les document_id disponibles. "
        "Retourne: liste des documents avec ID, filename, metadata."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, vector_store: QdrantVectorStore | None = None) -> None:
        """Initialise le tool.

        Args:
            vector_store: Instance partagee du vector store (injection).
        """
        super().__init__()
        self._vector_store = vector_store or QdrantVectorStore()

    async def _do_initialize(self) -> None:
        """Initialise le vector store."""
        await self._vector_store.initialize()

    async def _do_execute(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        """Liste tous les documents indexes.

        Args:
            arguments: Aucun parametre requis.

        Returns:
            Dictionnaire avec:
                - total_documents: Nombre de documents
                - documents: Liste des documents avec:
                    - document_id: ID unique
                    - filename: Nom du fichier
                    - title: Titre
                    - author: Auteur
                    - total_pages: Nombre de pages
                    - total_chunks: Nombre de chunks
                    - ingested_at: Date d'ingestion
        """
        logger.info("Listing indexed documents")

        # Recuperer la liste des documents
        documents = await self._vector_store.list_documents()

        logger.info("Found %d indexed documents", len(documents))

        return {
            "total_documents": len(documents),
            "documents": documents,
        }
