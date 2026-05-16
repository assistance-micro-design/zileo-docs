# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Tests d'integration pour QdrantVectorStore.

Ces tests necessitent une instance Qdrant en cours d'execution.
Ils sont marques comme integration tests et seront skipes si Qdrant
n'est pas disponible.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from qdrant_client import QdrantClient

from src.models.chunk import ChunkMetadata, DocumentChunk
from src.models.document import DocumentMetadata
from src.services.vector.qdrant_store import QdrantVectorStore


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# =============================================================================
# Constants
# =============================================================================

VECTOR_SIZE = 1024
TEST_COLLECTION_PREFIX = "test_integration_"


# =============================================================================
# Skip condition pour Qdrant non disponible
# =============================================================================


def is_qdrant_available() -> bool:
    """Verifie si Qdrant est disponible."""
    try:
        client = QdrantClient(host="localhost", port=6333, timeout=5)
        client.get_collections()
        return True
    except Exception:
        return False


qdrant_available = pytest.mark.skipif(
    not is_qdrant_available(),
    reason="Qdrant n'est pas disponible sur localhost:6333",
)


# =============================================================================
# Helpers
# =============================================================================


def generate_fake_embedding(seed: int = 0) -> list[float]:
    """Genere un embedding factice reproductible de 1024 dimensions.

    Args:
        seed: Graine pour la generation reproductible.

    Returns:
        Liste de 1024 floats normalises.
    """
    embedding = []
    for i in range(VECTOR_SIZE):
        value = math.sin(seed * 0.1 + i * 0.01) * 0.5 + 0.5
        embedding.append(value)

    # Normalisation L2
    norm = math.sqrt(sum(x * x for x in embedding))
    return [x / norm for x in embedding]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_collection_name() -> str:
    """Genere un nom de collection unique pour les tests."""
    unique_id = uuid.uuid4().hex[:8]
    return f"{TEST_COLLECTION_PREFIX}{unique_id}"


@pytest.fixture
async def vector_store(
    test_collection_name: str,
) -> AsyncGenerator[QdrantVectorStore, None]:
    """Fixture pour QdrantVectorStore avec collection de test isolee.

    Cree une collection unique pour chaque test et la supprime apres.
    """
    store = QdrantVectorStore(host="localhost", port=6333)
    # Override le nom de collection pour isolation
    store.COLLECTION_NAME = test_collection_name

    await store.initialize()

    yield store

    # Cleanup: supprimer la collection de test
    with contextlib.suppress(Exception):
        await asyncio.to_thread(
            store.client.delete_collection,
            collection_name=test_collection_name,
        )


@pytest.fixture
def sample_document_metadata() -> DocumentMetadata:
    """Cree des metadonnees de document de test."""
    return DocumentMetadata(
        document_id="doc-integration-test-001",
        file_hash="abcdef1234567890",
        filename="test_document.pdf",
        file_size_bytes=1024000,
        title="Document de Test Integration",
        author="Test Author",
        total_pages=10,
        ingested_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_document_metadata_2() -> DocumentMetadata:
    """Cree des metadonnees pour un second document de test."""
    return DocumentMetadata(
        document_id="doc-integration-test-002",
        file_hash="fedcba0987654321",
        filename="second_document.pdf",
        file_size_bytes=2048000,
        title="Second Document de Test",
        author="Another Author",
        total_pages=20,
        ingested_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_chunks(sample_document_metadata: DocumentMetadata) -> list[DocumentChunk]:
    """Cree des chunks de test avec embeddings factices."""
    doc_id = sample_document_metadata.document_id
    chunks = []

    # Chunk 1: Texte simple, page 1
    chunk1 = DocumentChunk(
        content="Ceci est le premier chunk avec du contenu textuel simple.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-001",
            document_id=doc_id,
            page_numbers=[1],
            start_page=1,
            end_page=1,
            section_title="Introduction",
            content_type="text",
            has_table=False,
            has_image=False,
            has_equation=False,
            token_count=50,
            char_count=60,
            word_count=10,
            chunk_index=0,
            total_chunks=5,
        ),
        embedding=generate_fake_embedding(seed=1),
    )
    chunks.append(chunk1)

    # Chunk 2: Avec tableau, pages 2-3
    chunk2 = DocumentChunk(
        content="Ce chunk contient un tableau de donnees financieres.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-002",
            document_id=doc_id,
            page_numbers=[2, 3],
            start_page=2,
            end_page=3,
            section_title="Donnees Financieres",
            content_type="table",
            has_table=True,
            has_image=False,
            has_equation=False,
            token_count=80,
            char_count=100,
            word_count=15,
            chunk_index=1,
            total_chunks=5,
        ),
        embedding=generate_fake_embedding(seed=2),
    )
    chunks.append(chunk2)

    # Chunk 3: Avec image, page 4
    chunk3 = DocumentChunk(
        content="Description de l'image montrant un graphique de performance.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-003",
            document_id=doc_id,
            page_numbers=[4],
            start_page=4,
            end_page=4,
            section_title="Graphiques",
            content_type="image_description",
            has_table=False,
            has_image=True,
            has_equation=False,
            token_count=60,
            char_count=70,
            word_count=11,
            chunk_index=2,
            total_chunks=5,
        ),
        embedding=generate_fake_embedding(seed=3),
    )
    chunks.append(chunk3)

    # Chunk 4: Avec equation, page 5
    chunk4 = DocumentChunk(
        content="La formule E = mc^2 represente l'equivalence masse-energie.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-004",
            document_id=doc_id,
            page_numbers=[5],
            start_page=5,
            end_page=5,
            section_title="Formules",
            content_type="text",
            has_table=False,
            has_image=False,
            has_equation=True,
            token_count=45,
            char_count=55,
            word_count=9,
            chunk_index=3,
            total_chunks=5,
        ),
        embedding=generate_fake_embedding(seed=4),
    )
    chunks.append(chunk4)

    # Chunk 5: Texte final, pages 8-10
    chunk5 = DocumentChunk(
        content="Conclusion du document avec un resume des points cles.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-005",
            document_id=doc_id,
            page_numbers=[8, 9, 10],
            start_page=8,
            end_page=10,
            section_title="Conclusion",
            content_type="text",
            has_table=False,
            has_image=False,
            has_equation=False,
            token_count=55,
            char_count=65,
            word_count=12,
            chunk_index=4,
            total_chunks=5,
        ),
        embedding=generate_fake_embedding(seed=5),
    )
    chunks.append(chunk5)

    return chunks


@pytest.fixture
def sample_chunks_doc2(
    sample_document_metadata_2: DocumentMetadata,
) -> list[DocumentChunk]:
    """Cree des chunks pour le second document."""
    doc_id = sample_document_metadata_2.document_id

    chunk = DocumentChunk(
        content="Contenu du second document pour tests de filtrage.",
        metadata=ChunkMetadata(
            chunk_id=f"{doc_id}-chunk-001",
            document_id=doc_id,
            page_numbers=[1],
            start_page=1,
            end_page=1,
            section_title="Introduction",
            content_type="text",
            has_table=False,
            has_image=False,
            has_equation=False,
            token_count=40,
            char_count=50,
            word_count=8,
            chunk_index=0,
            total_chunks=1,
        ),
        embedding=generate_fake_embedding(seed=100),
    )

    return [chunk]


# =============================================================================
# Tests d'integration
# =============================================================================


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_and_search(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test stockage de chunks et recherche semantique."""
    # Stocker les chunks
    result = await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    assert result["stored_chunks"] == 5
    assert result["skipped_chunks"] == 0
    assert result["document_id"] == sample_document_metadata.document_id

    # Rechercher avec un embedding similaire au chunk 1
    query_embedding = generate_fake_embedding(seed=1)
    search_results = await vector_store.search(
        query_embedding=query_embedding,
        top_k=3,
        score_threshold=0.5,
    )

    assert len(search_results) > 0
    # Le chunk 1 devrait etre le plus similaire (meme seed)
    assert search_results[0]["chunk_id"] == f"{sample_document_metadata.document_id}-chunk-001"
    assert search_results[0]["score"] > 0.9


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_by_document_id(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_chunks_doc2: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
    sample_document_metadata_2: DocumentMetadata,
) -> None:
    """Test filtrage par document_id."""
    # Stocker chunks des deux documents
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)
    await vector_store.store_chunks(sample_chunks_doc2, sample_document_metadata_2)

    # Rechercher uniquement dans le premier document
    query_embedding = generate_fake_embedding(seed=1)
    results = await vector_store.search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"document_id": sample_document_metadata.document_id},
        score_threshold=0.0,
    )

    # Tous les resultats doivent appartenir au premier document
    for result in results:
        assert result["document_id"] == sample_document_metadata.document_id

    # Verifier qu'on a bien 5 chunks du premier document
    assert len(results) == 5


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_by_content_type(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test filtrage par type de contenu."""
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    query_embedding = generate_fake_embedding(seed=2)

    # Filtrer par type "table"
    results = await vector_store.search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"content_type": "table"},
        score_threshold=0.0,
    )

    assert len(results) == 1
    assert results[0]["content_type"] == "table"
    assert "chunk-002" in results[0]["chunk_id"]


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_by_page_range(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test filtrage par plage de pages."""
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    query_embedding = generate_fake_embedding(seed=1)

    # Filtrer pages 1-3
    results = await vector_store.search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"page_range": (1, 3)},
        score_threshold=0.0,
    )

    # Chunks 1 (page 1) et 2 (pages 2-3) devraient etre retournes
    assert len(results) == 2
    for result in results:
        start_page = result["page_numbers"][0] if result["page_numbers"] else 0
        assert start_page >= 1
        assert start_page <= 3


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_filter_with_has_table(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test filtrage par presence de tableau."""
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    query_embedding = generate_fake_embedding(seed=2)

    # Filtrer chunks avec tableaux
    results = await vector_store.search(
        query_embedding=query_embedding,
        top_k=10,
        filters={"has_table": True},
        score_threshold=0.0,
    )

    assert len(results) == 1
    assert "chunk-002" in results[0]["chunk_id"]


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_document(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_chunks_doc2: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
    sample_document_metadata_2: DocumentMetadata,
) -> None:
    """Test suppression de document."""
    # Stocker chunks des deux documents
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)
    await vector_store.store_chunks(sample_chunks_doc2, sample_document_metadata_2)

    # Verifier que les deux documents sont presents
    stats_before = await vector_store.get_stats()
    assert stats_before["points_count"] == 6  # 5 + 1

    # Supprimer le premier document
    result = await vector_store.delete_document(sample_document_metadata.document_id)
    assert result == 1  # Operation reussie

    # Attendre un peu pour la propagation
    await asyncio.sleep(0.5)

    # Verifier que seul le second document reste
    chunks_doc1 = await vector_store.get_document_chunks(sample_document_metadata.document_id)
    assert len(chunks_doc1) == 0

    chunks_doc2 = await vector_store.get_document_chunks(sample_document_metadata_2.document_id)
    assert len(chunks_doc2) == 1


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_document_chunks(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test recuperation de tous les chunks d'un document."""
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    chunks = await vector_store.get_document_chunks(sample_document_metadata.document_id)

    assert len(chunks) == 5

    # Verifier que tous les chunks appartiennent au bon document
    for chunk in chunks:
        assert chunk["document_id"] == sample_document_metadata.document_id

    # Verifier la presence de certains champs
    chunk_ids = [c["chunk_id"] for c in chunks]
    assert f"{sample_document_metadata.document_id}-chunk-001" in chunk_ids
    assert f"{sample_document_metadata.document_id}-chunk-005" in chunk_ids


@qdrant_available
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_stats(
    vector_store: QdrantVectorStore,
    sample_chunks: list[DocumentChunk],
    sample_document_metadata: DocumentMetadata,
) -> None:
    """Test recuperation des statistiques de collection."""
    # Stats avant insertion
    stats_empty = await vector_store.get_stats()
    assert stats_empty["points_count"] == 0
    assert "status" in stats_empty

    # Stocker des chunks
    await vector_store.store_chunks(sample_chunks, sample_document_metadata)

    # Stats apres insertion
    stats = await vector_store.get_stats()

    assert stats["points_count"] == 5
    assert "status" in stats
    assert "indexed_vectors_count" in stats
