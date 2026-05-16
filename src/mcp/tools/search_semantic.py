# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tool MCP de recherche semantique pure (similarite cosinus dense)."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from src.mcp.tools.search_base import BaseSearchTool
from src.models.api import SearchSemanticParams


logger = logging.getLogger(__name__)


class SearchSemanticTool(BaseSearchTool):
    """Recherche semantique pure (similarite cosinus dense).

    Le mode semantic utilise uniquement l'embedding dense (Mistral 1024d)
    et la similarite cosinus. `score_threshold` (defaut 0.7) sert de
    garde-fou: les chunks dont le score cosinus n'atteint pas ce seuil
    sont filtres.

    Adapte aux questions abstraites/conceptuelles ou la reformulation
    semantique compte plus que la presence de termes exacts.
    """

    name: ClassVar[str] = "search_semantic"
    description: ClassVar[str] = (
        "Recherche semantique pure (similarite cosinus dense, defaut 0.7). "
        "Ideal pour questions abstraites/conceptuelles."
    )

    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "query": BaseSearchTool.QUERY_SCHEMA,
            "top_k": BaseSearchTool.TOP_K_SCHEMA,
            "score_threshold": {
                "type": "number",
                "description": (
                    "Seuil de similarite cosinus (0.0-1.0, defaut 0.7). Les chunks "
                    "dont le score ne depasse pas ce seuil sont filtres."
                ),
                "default": 0.7,
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "filters": BaseSearchTool.FILTERS_SCHEMA,
        },
        "required": ["query"],
    }

    async def _do_execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute la recherche semantique pure (dense + cosinus)."""
        params, query_embedding = await self._validate_and_embed_query(
            arguments, SearchSemanticParams
        )

        logger.info(
            "search_semantic: query_len=%d top_k=%d threshold=%.2f filter_keys=%s",
            len(params.query),
            params.top_k,
            params.score_threshold,
            sorted(params.filters.keys()) if params.filters else [],
        )

        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=params.top_k,
            filters=params.filters,
            score_threshold=params.score_threshold,
        )

        logger.info("search_semantic: %d resultats", len(results))
        return self._format_response(params.query, results)
