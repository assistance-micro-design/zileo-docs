"""Tool MCP pour la recherche semantique dans les documents."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.core.exceptions import EmptyQueryError
from src.models.api import SearchDocumentsParams
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.vector.qdrant_store import QdrantVectorStore


logger = logging.getLogger(__name__)


class SearchDocumentsTool:
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
        "Recherche dans les PDFs indexes par similarite semantique. "
        "Requiert: documents indexes via index_document. "
        "Retourne: passages pertinents avec score et numero de page."
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
                    "has_table": {
                        "type": "boolean",
                        "description": "True pour ne chercher que dans les passages avec tableaux",
                    },
                    "has_image": {
                        "type": "boolean",
                        "description": "True pour ne chercher que dans les passages avec images",
                    },
                },
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        """Initialise le tool de recherche."""
        self._embedder = MistralEmbedder()
        self._vector_store = QdrantVectorStore()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise le vector store.

        Doit etre appele avant execute() pour garantir
        que la connexion a Qdrant est etablie.
        """
        if not self._initialized:
            await self._vector_store.initialize()
            self._initialized = True

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
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
        # S'assurer que les services sont initialises
        if not self._initialized:
            await self.initialize()

        # Valider les parametres
        params = SearchDocumentsParams(**arguments)

        if not params.query or not params.query.strip():
            raise EmptyQueryError()

        logger.info(
            "Recherche: '%s' (top_k=%d, filters=%s)",
            params.query[:50],
            params.top_k,
            params.filters,
        )

        # Generer l'embedding de la requete
        query_embedding = await self._embedder.embed_query(params.query)

        # Rechercher dans Qdrant
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=params.top_k,
            filters=params.filters,
            score_threshold=0.7,
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
                }
                for r in results
            ],
        }
