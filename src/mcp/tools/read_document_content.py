# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Tool MCP pour lire le contenu complet d'un document indexe."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.core.exceptions import DocumentNotFoundError
from src.mcp.tools.base import BaseMCPTool
from src.models.api import ReadDocumentContentParams
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class ReadDocumentContentTool(BaseMCPTool):
    """Tool MCP pour lire le contenu Markdown d'un document indexe.

    Ce tool permet au LLM de recuperer le contenu complet d'un document
    prealablement indexe, avec possibilite de filtrer par pages.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = ReadDocumentContentTool()
        >>> await tool.initialize()
        >>> result = await tool.execute({"document_id": "doc-123"})
        >>> print(result["content"][:500])
    """

    name: ClassVar[str] = "read_document_content"
    description: ClassVar[str] = (
        "Lit le contenu Markdown complet d'un document indexe. "
        "Utiliser pour lire/analyser un document entier ou des pages specifiques. "
        "Retourne: contenu Markdown, nombre de tokens, pages."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": (
                    "ID du document (retourne par index_document ou list_indexed_documents). "
                    "Ex: 'doc-abc123'"
                ),
            },
            "page_start": {
                "type": "integer",
                "minimum": 1,
                "description": "Page de debut (1-indexed). Optionnel, defaut: premiere page.",
            },
            "page_end": {
                "type": "integer",
                "minimum": 1,
                "description": "Page de fin (1-indexed). Optionnel, defaut: derniere page.",
            },
            "include_chunks_detail": {
                "type": "boolean",
                "default": False,
                "description": "Inclure les metadonnees de chaque chunk.",
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
        """Lit le contenu d'un document indexe.

        Args:
            arguments: Parametres:
                - document_id: ID du document
                - page_start: Page de debut (optionnel)
                - page_end: Page de fin (optionnel)
                - include_chunks_detail: Inclure details (optionnel)

        Returns:
            Dictionnaire avec:
                - document_id, filename
                - total_pages, total_chunks, total_tokens
                - pages_returned, chunks_returned, tokens_returned
                - content: Markdown complet
                - chunks_detail: Metadonnees par chunk (si demande)

        Raises:
            DocumentNotFoundError: Si le document n'existe pas.
        """
        # Valider les parametres
        params = ReadDocumentContentParams(**arguments)

        logger.info(
            "Lecture document: %s (pages %s-%s)",
            params.document_id,
            params.page_start or "debut",
            params.page_end or "fin",
        )

        # Recuperer tous les chunks du document
        chunks = await self._vector_store.get_document_chunks(params.document_id)

        if not chunks:
            raise DocumentNotFoundError(params.document_id)

        # Trier par chunk_index
        chunks_sorted = sorted(chunks, key=lambda c: c.get("chunk_index", 0))

        # Calculer stats du document complet
        total_tokens = sum(c.get("token_count", 0) for c in chunks_sorted)
        total_chars = sum(c.get("char_count", 0) for c in chunks_sorted)

        # Extraire metadonnees du premier chunk
        first_chunk = chunks_sorted[0]
        total_pages = first_chunk.get("doc_total_pages", 0)

        # Filtrer par pages si demande
        if params.page_start is not None or params.page_end is not None:
            start = (params.page_start or 1) - 1  # Convertir en 0-indexed
            end = params.page_end or total_pages

            chunks_filtered = [
                c
                for c in chunks_sorted
                if any(start <= p <= end - 1 for p in c.get("page_numbers", []))
            ]
        else:
            chunks_filtered = chunks_sorted

        # Collecter les pages retournees
        pages_set: set[int] = set()
        for c in chunks_filtered:
            pages_set.update(c.get("page_numbers", []))
        pages_returned = sorted(p + 1 for p in pages_set)  # Convertir en 1-indexed

        # Concatener le contenu
        content_parts: list[str] = []
        for chunk in chunks_filtered:
            chunk_content = chunk.get("content", "")
            if chunk_content:
                content_parts.append(chunk_content)

        content = "\n\n".join(content_parts)

        # Calculer stats de la selection
        tokens_returned = sum(c.get("token_count", 0) for c in chunks_filtered)

        logger.info(
            "Document %s: %d chunks/%d, %d tokens/%d",
            params.document_id,
            len(chunks_filtered),
            len(chunks_sorted),
            tokens_returned,
            total_tokens,
        )

        # Construire la reponse
        result: dict[str, Any] = {
            # Identifiants
            "document_id": params.document_id,
            "filename": first_chunk.get("doc_filename"),
            # Stats document complet
            "total_pages": total_pages,
            "total_chunks": len(chunks_sorted),
            "total_tokens": total_tokens,
            "total_chars": total_chars,
            # Stats selection
            "pages_returned": pages_returned,
            "chunks_returned": len(chunks_filtered),
            "tokens_returned": tokens_returned,
            # Contenu
            "content": content,
        }

        # Ajouter details des chunks si demande
        if params.include_chunks_detail:
            result["chunks_detail"] = [
                {
                    "chunk_index": c.get("chunk_index"),
                    "page_numbers": [p + 1 for p in c.get("page_numbers", [])],
                    "section_title": c.get("section_title"),
                    "content_type": c.get("content_type"),
                    "token_count": c.get("token_count", 0),
                    "has_table": c.get("has_table", False),
                    "has_image": c.get("has_image", False),
                }
                for c in chunks_filtered
            ]

        return result
