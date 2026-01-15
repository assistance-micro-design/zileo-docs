"""Tool MCP pour obtenir les informations d'un document."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.base import BaseMCPTool
from src.models.api import GetDocumentParams
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class GetDocumentTool(BaseMCPTool):
    """Tool MCP pour obtenir les informations d'un document indexe.

    Ce tool permet de recuperer les metadonnees et les chunks
    d'un document prealablement indexe dans la base vectorielle.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = GetDocumentTool()
        >>> await tool.initialize()
        >>> info = await tool.execute({"document_id": "doc-123"})
        >>> print(f"Document: {info['filename']}, {info['total_chunks']} chunks")
    """

    name: ClassVar[str] = "get_document"
    description: ClassVar[str] = (
        "Recupere les infos d'un document deja indexe. "
        "Utiliser pour verifier si un document existe ou voir son contenu. "
        "Retourne: metadonnees, nombre de pages, apercu des passages."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "ID du document (retourne par index_document). Ex: 'doc-abc123'",
            },
        },
        "required": ["document_id"],
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

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Recupere les informations d'un document.

        Args:
            arguments: Parametres:
                - document_id: ID du document

        Returns:
            Dictionnaire avec:
                - document_id: ID du document
                - filename: Nom du fichier
                - title: Titre du document
                - author: Auteur
                - total_pages: Nombre de pages
                - total_chunks: Nombre de chunks
                - ingested_at: Date d'ingestion
                - chunks: Liste des chunks avec apercu

        Raises:
            DocumentNotFoundError: Si le document n'existe pas.
        """
        # Valider les parametres
        params = GetDocumentParams(**arguments)

        logger.info("Recuperation document: %s", params.document_id)

        # Recuperer les chunks du document
        chunks = await self._vector_store.get_document_chunks(params.document_id)

        if not chunks:
            raise DocumentNotFoundError(params.document_id)

        # Extraire les metadonnees du premier chunk
        first_chunk = chunks[0]

        # Calculer des statistiques
        total_tokens = sum(c.get("token_count", 0) for c in chunks)
        content_types = list({c.get("content_type", "text") for c in chunks})

        logger.info(
            "Document %s: %d chunks, %d tokens",
            params.document_id,
            len(chunks),
            total_tokens,
        )

        # Construire la reponse
        return {
            "document_id": params.document_id,
            "filename": first_chunk.get("doc_filename"),
            "title": first_chunk.get("doc_title"),
            "author": first_chunk.get("doc_author"),
            "total_pages": first_chunk.get("doc_total_pages"),
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "content_types": content_types,
            "ingested_at": first_chunk.get("ingested_at"),
            "file_hash": first_chunk.get("doc_file_hash"),
            "chunks": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "chunk_index": c.get("chunk_index"),
                    "content_preview": c.get("content_preview", "")[:200],
                    "page_numbers": c.get("page_numbers", []),
                    "section_title": c.get("section_title"),
                    "content_type": c.get("content_type"),
                    "token_count": c.get("token_count", 0),
                    "has_table": c.get("has_table", False),
                    "has_image": c.get("has_image", False),
                }
                for c in chunks
            ],
        }
