"""Services de stockage vectoriel.

Ce module expose les services de stockage vectoriel pour les embeddings
de documents PDF.
"""

from __future__ import annotations

from src.services.vector.qdrant_store import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    QdrantVectorStore,
)


__all__ = [
    "COLLECTION_NAME",
    "VECTOR_SIZE",
    "QdrantVectorStore",
]
