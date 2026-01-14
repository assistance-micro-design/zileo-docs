"""Injection de dependances pour l'API FastAPI.

Ce module fournit les fonctions de dependance pour injecter
les services dans les endpoints FastAPI.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.pipeline.orchestrator import PDFPipelineOrchestrator
from src.services.vector.qdrant_store import QdrantVectorStore


@lru_cache
def get_orchestrator() -> PDFPipelineOrchestrator:
    """Retourne une instance singleton de l'orchestrateur.

    Returns:
        PDFPipelineOrchestrator configure avec les settings par defaut.
    """
    return PDFPipelineOrchestrator()


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


# Type aliases pour injection de dependances
OrchestratorDep = Annotated[PDFPipelineOrchestrator, Depends(get_orchestrator)]
VectorStoreDep = Annotated[QdrantVectorStore, Depends(get_vector_store)]
EmbedderDep = Annotated[MistralEmbedder, Depends(get_embedder)]
