# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Models pour les requetes et resultats de recherche."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """Filtres de recherche pour affiner les resultats.

    Attributes:
        document_id: Filtrer par document specifique.
        content_type: Filtrer par type de contenu.
        page_range: Filtrer par plage de pages.
    """

    document_id: str | None = None
    content_type: str | None = None
    page_range: tuple[int, int] | None = None
    has_table: bool | None = None
    has_image: bool | None = None
    section_title: str | None = None
    text_search: str | None = None
    doc_filename: str | None = None


class SearchQuery(BaseModel):
    """Requete de recherche semantique.

    Attributes:
        query: Texte de recherche.
        top_k: Nombre de resultats a retourner.
        score_threshold: Seuil minimum de score de similarite.
        filters: Filtres optionnels.
    """

    query: Annotated[str, Field(min_length=1, description="Texte de recherche")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100)]
    score_threshold: Annotated[float, Field(default=0.7, ge=0.0, le=1.0)]
    filters: SearchFilters | None = None
    search_mode: Annotated[
        Literal["hybrid", "semantic"],
        Field(
            default="hybrid",
            description="Mode: 'hybrid' (vecteur+full-text) ou 'semantic' (vecteur seul)",
        ),
    ]


class SearchResultItem(BaseModel):
    """Resultat de recherche individuel.

    Attributes:
        chunk_id: Identifiant du chunk.
        document_id: Identifiant du document source.
        content: Contenu du chunk.
        score: Score de similarite.
    """

    chunk_id: str
    document_id: str
    content: str
    content_preview: str
    score: float

    # Localisation
    page_numbers: list[int]
    section_title: str | None

    # Type
    content_type: str

    # Document
    doc_filename: str


class SearchResponse(BaseModel):
    """Reponse complete de recherche.

    Attributes:
        query: Requete originale.
        total_results: Nombre total de resultats.
        results: Liste des resultats.
        processing_time_ms: Temps de traitement en millisecondes.
    """

    query: str
    total_results: int
    results: list[SearchResultItem]
    processing_time_ms: int
