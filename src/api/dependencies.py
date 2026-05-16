# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Injection de dependances pour l'API FastAPI.

Ce module fournit les fonctions de dependance pour injecter
les services dans les endpoints FastAPI.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.embedding.sparse_embedder import SparseEmbedder
from src.services.pipeline.orchestrator import DocumentPipelineOrchestrator
from src.services.vector.qdrant_store import QdrantVectorStore


@lru_cache
def get_vector_store() -> QdrantVectorStore:
    """Retourne une instance singleton du vector store.

    Returns:
        QdrantVectorStore configure avec les settings par defaut.
    """
    return QdrantVectorStore()


@lru_cache
def get_embedder() -> MistralEmbedder:
    """Retourne une instance singleton de l'embedder.

    Returns:
        MistralEmbedder configure avec les settings par defaut.
    """
    return MistralEmbedder()


@lru_cache
def get_sparse_embedder() -> SparseEmbedder:
    """Retourne une instance singleton du sparse embedder BM25.

    Returns:
        SparseEmbedder configure avec le modele par defaut.
    """
    return SparseEmbedder()


@lru_cache
def get_orchestrator() -> DocumentPipelineOrchestrator:
    """Retourne une instance singleton de l'orchestrateur avec DI partagee.

    Returns:
        DocumentPipelineOrchestrator partageant les singletons vector_store/embedders.
    """
    return DocumentPipelineOrchestrator(
        vector_store=get_vector_store(),
        embedder=get_embedder(),
        sparse_embedder=get_sparse_embedder(),
    )


# Type aliases pour injection de dependances
OrchestratorDep = Annotated[DocumentPipelineOrchestrator, Depends(get_orchestrator)]
VectorStoreDep = Annotated[QdrantVectorStore, Depends(get_vector_store)]
EmbedderDep = Annotated[MistralEmbedder, Depends(get_embedder)]
SparseEmbedderDep = Annotated[SparseEmbedder, Depends(get_sparse_embedder)]
