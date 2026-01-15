"""Tool MCP pour la recherche semantique dans les documents."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.core.exceptions import EmptyQueryError
from src.mcp.tools.base import BaseMCPTool
from src.models.api import SearchDocumentsParams
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class SearchDocumentsTool(BaseMCPTool):
    """Tool MCP pour la recherche semantique dans les documents indexes.

    Ce tool permet de rechercher des informations dans les documents
    PDF prealablement indexes en utilisant la similarite semantique.

    Attributes:
        name: Nom du tool MCP.
        description: Description du tool.
        input_schema: Schema JSON des parametres.

    Example:
        >>> tool = SearchDocumentsTool()
        >>> await tool.initialize()
        >>> results = await tool.execute(
        ...     {"query": "comment configurer l'authentification?", "top_k": 5}
        ... )
    """

    name: ClassVar[str] = "search_documents"
    description: ClassVar[str] = (
        "Recherche dans les documents indexes (PDF/Excel/Word) par similarite semantique. "
        "Requiert: documents indexes via index_document. "
        "Retourne: passages pertinents avec score, page et type de document. "
        "Supporte filtres: document_type, has_formula, sheet_name."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Question en langage naturel. Ex: 'comment configurer X?'",
            },
            "top_k": {
                "type": "integer",
                "description": "Nombre de passages a retourner (1-100, defaut: 5)",
                "default": 5,
                "minimum": 1,
                "maximum": 100,
            },
            "score_threshold": {
                "type": "number",
                "description": "Score minimum de similarite (0.0-1.0, defaut: 0.7). Baisser pour plus de resultats.",
                "default": 0.7,
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "filters": {
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
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedder: MistralEmbedder | None = None,
    ) -> None:
        """Initialise le tool de recherche.

        Args:
            vector_store: Instance partagee du vector store (injection).
            embedder: Instance partagee de l'embedder (injection).
        """
        super().__init__()
        self._embedder = embedder or MistralEmbedder()
        self._vector_store = vector_store or QdrantVectorStore()

    async def _do_initialize(self) -> None:
        """Initialise le vector store."""
        await self._vector_store.initialize()

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la recherche semantique.

        Args:
            arguments: Parametres de recherche:
                - query: Requete en langage naturel
                - top_k: Nombre de resultats (optionnel)
                - filters: Filtres optionnels

        Returns:
            Dictionnaire avec:
                - query: Requete originale
                - total_results: Nombre de resultats
                - results: Liste des resultats avec:
                    - chunk_id: ID du chunk
                    - document_id: ID du document
                    - content: Contenu du chunk
                    - score: Score de similarite
                    - page_numbers: Pages du chunk
                    - section_title: Titre de section
                    - doc_filename: Nom du fichier

        Raises:
            EmptyQueryError: Si la requete est vide.
            NoResultsError: Si aucun resultat n'est trouve.
        """
        # Valider les parametres
        params = SearchDocumentsParams(**arguments)

        if not params.query or not params.query.strip():
            raise EmptyQueryError()

        logger.info(
            "Recherche: '%s' (top_k=%d, threshold=%.2f, filters=%s)",
            params.query[:50],
            params.top_k,
            params.score_threshold,
            params.filters,
        )

        # Generer l'embedding de la requete
        query_embedding = await self._embedder.embed_query(params.query)

        # Rechercher dans Qdrant
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=params.top_k,
            filters=params.filters,
            score_threshold=params.score_threshold,
        )

        logger.info("Recherche terminee: %d resultats", len(results))

        # Construire la reponse
        return {
            "query": params.query,
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
                    # Nouveaux champs multi-format
                    "document_type": r.get("document_type", "pdf"),
                    "has_formula": r.get("has_formula", False),
                    "sheet_names": r.get("sheet_names", []),
                }
                for r in results
            ],
        }
