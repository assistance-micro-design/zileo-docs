# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests pour src/api/dependencies.py (DI singletons FastAPI)."""

from __future__ import annotations

import pytest

from src.api import dependencies
from src.services.embedding.mistral_embedder import MistralEmbedder
from src.services.embedding.sparse_embedder import SparseEmbedder
from src.services.pipeline.orchestrator import DocumentPipelineOrchestrator
from src.services.vector.qdrant_store import QdrantVectorStore


@pytest.fixture(autouse=True)
def _clear_lru_caches() -> None:
    """Vide les caches lru entre les tests pour isolation."""
    dependencies.get_vector_store.cache_clear()
    dependencies.get_embedder.cache_clear()
    dependencies.get_sparse_embedder.cache_clear()
    dependencies.get_orchestrator.cache_clear()


def test_get_vector_store_is_singleton() -> None:
    """get_vector_store() retourne la meme instance (lru_cache)."""
    first = dependencies.get_vector_store()
    second = dependencies.get_vector_store()

    assert first is second
    assert isinstance(first, QdrantVectorStore)


def test_get_embedder_is_singleton() -> None:
    """get_embedder() retourne la meme instance (lru_cache)."""
    first = dependencies.get_embedder()
    second = dependencies.get_embedder()

    assert first is second
    assert isinstance(first, MistralEmbedder)


def test_get_sparse_embedder_is_singleton() -> None:
    """get_sparse_embedder() retourne la meme instance (lru_cache)."""
    first = dependencies.get_sparse_embedder()
    second = dependencies.get_sparse_embedder()

    assert first is second
    assert isinstance(first, SparseEmbedder)


def test_get_orchestrator_shares_vector_store_singleton() -> None:
    """get_orchestrator() injecte le singleton get_vector_store() (DI partagee)."""
    vector_store = dependencies.get_vector_store()
    orchestrator = dependencies.get_orchestrator()

    assert isinstance(orchestrator, DocumentPipelineOrchestrator)
    assert orchestrator.vector_store is vector_store


def test_get_orchestrator_is_singleton() -> None:
    """get_orchestrator() retourne la meme instance entre appels."""
    first = dependencies.get_orchestrator()
    second = dependencies.get_orchestrator()

    assert first is second
