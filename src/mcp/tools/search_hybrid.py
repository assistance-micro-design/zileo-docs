# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP de recherche hybride (dense + BM25 + RRF) avec garde-fou cosinus."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.search_base import BaseSearchTool
from src.models.api import SearchHybridParams


logger = logging.getLogger(__name__)


class SearchHybridTool(BaseSearchTool):
    """Recherche hybride (dense vecteur + BM25 sparse, fusion RRF).

    Le mode hybrid combine la similarite semantique dense (Mistral 1024d)
    avec la recherche full-text BM25 (fastembed) et fusionne les listes
    via Reciprocal Rank Fusion. L'echelle de score RRF (non interpretable
    cross-corpus) est masquee au caller MCP.

    Un garde-fou optionnel `min_cosine_relevance` peut etre passe: si le
    top-1 en similarite cosinus dense ne depasse pas ce seuil, la recherche
    renvoie une liste vide. Cela coupe les queries hors-domaine
    (calibration empirique: 0.72).
    """

    name: ClassVar[str] = "search_hybrid"
    description: ClassVar[str] = (
        "Recherche hybride (dense+BM25 fusion RRF) dans les documents indexes. "
        "Optionnel: min_cosine_relevance comme garde-fou anti hors-domaine."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": BaseSearchTool.QUERY_SCHEMA,
            "top_k": BaseSearchTool.TOP_K_SCHEMA,
            "min_cosine_relevance": {
                "type": "number",
                "description": (
                    "Garde-fou cosinus (opt-in, 0.0-1.0). Si le top-1 en similarite cosinus "
                    "dense ne depasse pas ce seuil, retourne liste vide. Evite les faux "
                    "positifs hors-domaine (calibre empirique: 0.72)."
                ),
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "filters": BaseSearchTool.FILTERS_SCHEMA,
        },
        "required": ["query"],
    }

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la recherche hybride (garde-fou cosinus optionnel)."""
        params, query_embedding = await self._validate_and_embed_query(
            arguments, SearchHybridParams
        )

        logger.info(
            "search_hybrid: query_len=%d top_k=%d min_cosine=%s filter_keys=%s",
            len(params.query),
            params.top_k,
            params.min_cosine_relevance,
            sorted(params.filters.keys()) if params.filters else [],
        )

        if params.min_cosine_relevance is not None:
            guard = await self._vector_store.search(
                query_embedding=query_embedding,
                top_k=1,
                filters=params.filters,
                score_threshold=params.min_cosine_relevance,
            )
            if not guard:
                logger.info(
                    "search_hybrid garde-fou: top-1 < %.2f, retour liste vide",
                    params.min_cosine_relevance,
                )
                return self._format_response(params.query, [])

        sparse_data = await self._sparse_embedder.embed_query(params.query)
        results = await self._vector_store.hybrid_search(
            query_embedding=query_embedding,
            sparse_embedding=sparse_data,
            top_k=params.top_k,
            filters=params.filters,
        )

        logger.info("search_hybrid: %d resultats", len(results))
        return self._format_response(params.query, results)
