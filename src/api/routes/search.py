# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Routes API pour la recherche semantique."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.dependencies import EmbedderDep, VectorStoreDep
from src.core.config import settings
from src.models.search import SearchFilters, SearchQuery, SearchResponse, SearchResultItem


logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "",
    response_model=SearchResponse,
    summary="Recherche semantique",
    description="Recherche semantique dans les documents indexes.",
)
@limiter.limit(settings.RATE_LIMIT_SEARCH)  # type: ignore[untyped-decorator]
async def search_documents(
    request: Request,
    query: SearchQuery,
    embedder: EmbedderDep,
    vector_store: VectorStoreDep,
) -> SearchResponse:
    """Execute une recherche semantique dans les documents.

    Args:
        query: Parametres de recherche.
        embedder: Service d'embedding injecte.
        vector_store: Service de stockage vectoriel injecte.

    Returns:
        Resultats de recherche avec scores de similarite.

    Raises:
        HTTPException: Si la requete est invalide.
    """
    start_time = time.perf_counter()

    try:
        # Generer l'embedding de la requete
        query_embedding = await embedder.embed_query(query.query)

        # Construire les filtres Qdrant
        filters = _build_filters(query.filters) if query.filters else None

        # Rechercher dans Qdrant
        results = await vector_store.search(
            query_embedding=query_embedding,
            top_k=query.top_k,
            filters=filters,
            score_threshold=query.score_threshold,
        )

        # Convertir en modeles de reponse
        result_items = [
            SearchResultItem(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                content=r["content"],
                content_preview=r.get("content_preview", r["content"][:200]),
                score=r["score"],
                page_numbers=r.get("page_numbers", []),
                section_title=r.get("section_title"),
                content_type=r.get("content_type", "text"),
                doc_filename=r.get("doc_filename", ""),
            )
            for r in results
        ]

        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        return SearchResponse(
            query=query.query,
            total_results=len(result_items),
            results=result_items,
            processing_time_ms=processing_time_ms,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=SearchResponse,
    summary="Recherche semantique (GET)",
    description="Recherche semantique avec parametres en query string.",
)
@limiter.limit(settings.RATE_LIMIT_SEARCH)  # type: ignore[untyped-decorator]
async def search_documents_get(
    request: Request,
    embedder: EmbedderDep,
    vector_store: VectorStoreDep,
    q: str = Query(..., min_length=1, description="Texte de recherche"),
    top_k: int = Query(default=5, ge=1, le=100, description="Nombre de resultats"),
    score_threshold: float = Query(default=0.7, ge=0.0, le=1.0, description="Score minimum"),
    document_id: str | None = Query(default=None, description="Filtrer par document"),
    content_type: str | None = Query(default=None, description="Filtrer par type"),
    has_table: bool | None = Query(default=None, description="Filtrer tableaux"),
    has_image: bool | None = Query(default=None, description="Filtrer images"),
) -> SearchResponse:
    """Execute une recherche semantique via GET.

    Args:
        embedder: Service d'embedding injecte.
        vector_store: Service de stockage vectoriel injecte.
        q: Texte de recherche.
        top_k: Nombre de resultats.
        score_threshold: Score minimum de similarite.
        document_id: Filtrer par document.
        content_type: Filtrer par type de contenu.
        has_table: Filtrer les chunks avec tableaux.
        has_image: Filtrer les chunks avec images.

    Returns:
        Resultats de recherche.
    """
    # Construire les filtres
    filters = SearchFilters(
        document_id=document_id,
        content_type=content_type,
        has_table=has_table,
        has_image=has_image,
    )

    # Construire la requete
    query = SearchQuery(
        query=q,
        top_k=top_k,
        score_threshold=score_threshold,
        filters=filters if any([document_id, content_type, has_table, has_image]) else None,
    )

    return await search_documents(request, query, embedder, vector_store)  # type: ignore[no-any-return]


def _build_filters(filters: SearchFilters) -> dict[str, Any]:
    """Convertit les filtres en format Qdrant.

    Args:
        filters: Filtres de recherche.

    Returns:
        Dictionnaire de filtres pour Qdrant.
    """
    qdrant_filters: dict[str, Any] = {}

    if filters.document_id:
        qdrant_filters["document_id"] = filters.document_id

    if filters.content_type:
        qdrant_filters["content_type"] = filters.content_type

    if filters.page_range:
        qdrant_filters["page_range"] = filters.page_range

    if filters.has_table is not None:
        qdrant_filters["has_table"] = filters.has_table

    if filters.has_image is not None:
        qdrant_filters["has_image"] = filters.has_image

    if filters.section_title:
        qdrant_filters["section_title"] = filters.section_title

    if filters.text_search:
        qdrant_filters["text_search"] = filters.text_search

    if filters.doc_filename:
        qdrant_filters["doc_filename"] = filters.doc_filename

    return qdrant_filters
