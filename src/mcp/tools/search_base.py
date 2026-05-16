# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Classe de base factorisant la logique des tools de recherche MCP."""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel

from src.core.exceptions import EmptyQueryError
from src.mcp.tools.base import VectorStoreMCPTool
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.embedding.sparse_embedder import SparseEmbedder
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


SearchParamsT = TypeVar("SearchParamsT", bound=BaseModel)


class BaseSearchTool(VectorStoreMCPTool):
    """Classe de base pour les tools de recherche (hybrid + semantic).

    Factorise:
    - DI partagee (vector_store, embedder, sparse_embedder)
    - Validation Pydantic du query et embedding dense
    - Formatage de la reponse au format MCP standard
    - Schema JSON-RPC commun (champs query, top_k, filters)

    Les sous-classes implementent uniquement la logique specifique du mode
    (dispatch vers vector_store.search ou vector_store.hybrid_search,
    application d'un eventuel garde-fou cosinus).
    """

    QUERY_SCHEMA: ClassVar[dict[str, Any]] = {
        "type": "string",
        "description": "Question en langage naturel. Ex: 'comment configurer X?'",
    }

    TOP_K_SCHEMA: ClassVar[dict[str, Any]] = {
        "type": "integer",
        "description": "Nombre de passages a retourner (1-100, defaut: 5)",
        "default": 5,
        "minimum": 1,
        "maximum": 100,
    }

    FILTERS_SCHEMA: ClassVar[dict[str, Any]] = {
        "type": "object",
        "description": "Filtres optionnels pour affiner la recherche",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "Limiter a un document specifique (ID retourne par index_document)",
            },
            "doc_filename": {
                "type": "string",
                "description": "Limiter par nom de fichier. Ex: 'rapport.pdf'",
            },
            "document_type": {
                "type": "string",
                "enum": ["pdf", "excel", "word"],
                "description": "Filtrer par type de document (pdf/excel/word)",
            },
            "has_table": {
                "type": "boolean",
                "description": "True pour ne chercher que dans les passages avec tableaux",
            },
            "has_image": {
                "type": "boolean",
                "description": "True pour ne chercher que dans les passages avec images",
            },
            "has_formula": {
                "type": "boolean",
                "description": "Excel uniquement: True pour chunks avec formules",
            },
            "text_search": {
                "type": "string",
                "description": "Recherche full-text exacte dans le contenu (pour noms, mots-cles)",
            },
            "sheet_name": {
                "type": "string",
                "description": "Excel uniquement: filtrer par nom de feuille",
            },
        },
    }

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedder: MistralEmbedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
    ) -> None:
        """Initialise le tool avec DI des dependances de recherche.

        Args:
            vector_store: Instance partagee du vector store (injection).
            embedder: Instance partagee de l'embedder dense (injection).
            sparse_embedder: Instance partagee de l'embedder sparse (injection).
        """
        super().__init__(vector_store=vector_store)
        self._embedder = embedder or MistralEmbedder()
        self._sparse_embedder = sparse_embedder or SparseEmbedder()

    async def _validate_and_embed_query(
        self,
        arguments: dict[str, Any],
        params_cls: type[SearchParamsT],
    ) -> tuple[SearchParamsT, list[float]]:
        """Valide les arguments puis genere l'embedding dense de la query.

        Args:
            arguments: Arguments bruts recus du caller MCP.
            params_cls: Classe Pydantic des parametres a valider.

        Returns:
            Tuple (params valides, embedding dense de la query).

        Raises:
            EmptyQueryError: Si la query est vide ou whitespace uniquement.
        """
        params = params_cls(**arguments)
        query: str = params.query  # type: ignore[attr-defined]
        if not query or not query.strip():
            raise EmptyQueryError()
        query_embedding = await self._embedder.embed_query(query)
        return params, query_embedding

    def _format_response(self, query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Formate la liste de resultats en reponse MCP standard.

        Args:
            query: Requete originale.
            results: Resultats bruts retournes par le vector store.

        Returns:
            Reponse normalisee (query, total_results, results).
        """
        return {
            "query": query,
            "total_results": len(results),
            "results": [
                {
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "content": r["content"],
                    "content_preview": r.get("content_preview", r["content"][:200]),
                    "score": round(r["score"], 4),
                    "page_numbers": r.get("page_numbers", []),
                    "section_title": r.get("section_title"),
                    "content_type": r.get("content_type"),
                    "doc_filename": r.get("doc_filename"),
                    "document_type": r.get("document_type", "pdf"),
                    "has_formula": r.get("has_formula", False),
                    "sheet_names": r.get("sheet_names", []),
                }
                for r in results
            ],
        }

    @abstractmethod
    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Logique specifique du tool de recherche (a implementer)."""
