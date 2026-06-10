# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Service d'embedding sparse avec fastembed BM25.

Ce module fournit un service pour generer des embeddings sparse
(indices + poids) via le modele BM25 de fastembed, execute en local.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastembed import SparseTextEmbedding

    from src.models.chunk import DocumentChunk
    from src.services.embedding.mistral_embedder import MistralEmbedder

logger = logging.getLogger(__name__)


def _to_list(data: Any) -> list[Any]:
    """Convertit numpy array ou list en list Python."""
    return data.tolist() if hasattr(data, "tolist") else list(data)


def _to_sparse_data(raw: Any) -> SparseEmbeddingData:
    """Convertit un SparseEmbedding fastembed en SparseEmbeddingData."""
    return SparseEmbeddingData(
        indices=_to_list(raw.indices),
        values=_to_list(raw.values),
    )


@dataclass
class SparseEmbeddingData:
    """Embedding sparse (indices de tokens + poids).

    Format intermediaire entre fastembed et qdrant_client.SparseVector.

    Attributes:
        indices: Indices des tokens non-nuls dans le vocabulaire.
        values: Poids associes a chaque token.
    """

    indices: list[int]
    values: list[float]


class SparseEmbedder:
    """Generation d'embeddings sparse avec BM25 via fastembed.

    Le modele est charge en lazy (au premier appel) pour eviter
    le cout de chargement si le service n'est pas utilise.

    Attributes:
        MODEL: Nom du modele sparse fastembed.

    Example:
        >>> embedder = SparseEmbedder()
        >>> sparse = await embedder.embed_query("securite des donnees")
        >>> print(sparse.indices, sparse.values)
    """

    MODEL: str = "Qdrant/bm25"

    def __init__(self, model_name: str | None = None) -> None:
        """Initialise le service (sans charger le modele).

        Args:
            model_name: Nom du modele sparse. Defaut: Qdrant/bm25.
        """
        self._model_name = model_name or self.MODEL
        self._model: SparseTextEmbedding | None = None

        logger.debug("SparseEmbedder configure avec modele=%s (lazy)", self._model_name)

    def _ensure_model(self) -> SparseTextEmbedding:
        """Charge le modele si necessaire (lazy init)."""
        if self._model is not None:
            return self._model

        from fastembed import SparseTextEmbedding  # noqa: PLC0415

        logger.info("Chargement du modele sparse %s...", self._model_name)
        self._model = SparseTextEmbedding(model_name=self._model_name)
        logger.info("Modele sparse charge")
        return self._model

    async def embed_query(self, query: str) -> SparseEmbeddingData:
        """Genere un embedding sparse pour une requete de recherche.

        Utilise query_embed() de fastembed (optimise pour les requetes).

        Args:
            query: Texte de la requete.

        Returns:
            SparseEmbeddingData avec indices et values.

        Raises:
            ValueError: Si la requete est vide.
        """
        if not query or not query.strip():
            raise ValueError("La requete ne peut pas etre vide")

        query = query.strip()
        model = await asyncio.to_thread(self._ensure_model)
        raw = await asyncio.to_thread(lambda: next(iter(model.query_embed([query]))))

        return _to_sparse_data(raw)

    async def embed_texts(self, texts: list[str]) -> list[SparseEmbeddingData]:
        """Genere des embeddings sparse pour une liste de textes.

        Utilise embed() de fastembed (optimise pour les documents).

        Args:
            texts: Liste des textes a embedder.

        Returns:
            Liste de SparseEmbeddingData dans le meme ordre.
        """
        if not texts:
            return []

        model = await asyncio.to_thread(self._ensure_model)
        raw_embeddings = await asyncio.to_thread(lambda: list(model.embed(texts)))

        return [_to_sparse_data(emb) for emb in raw_embeddings]

    async def embed_chunks(self, chunks: Sequence[DocumentChunk]) -> list[DocumentChunk]:
        """Genere des embeddings sparse pour des DocumentChunks.

        Remplit le champ sparse_embedding de chaque chunk.

        Args:
            chunks: Liste des chunks a enrichir.

        Returns:
            Liste des memes chunks avec sparse_embedding rempli.
        """
        if not chunks:
            return []

        texts = [chunk.content for chunk in chunks]
        sparse_embeddings = await self.embed_texts(texts)

        chunks_list = list(chunks)
        for chunk, sparse in zip(chunks_list, sparse_embeddings, strict=True):
            chunk.sparse_embedding = sparse

        logger.info("Sparse embedding termine: %d chunks", len(chunks_list))
        return chunks_list


async def embed_dense_and_sparse(
    chunks: Sequence[DocumentChunk],
    dense_embedder: MistralEmbedder,
    sparse_embedder: SparseEmbedder,
) -> list[DocumentChunk]:
    """Genere les embeddings dense (Mistral) et sparse (BM25) en parallele.

    Args:
        chunks: Chunks a enrichir.
        dense_embedder: Embedder dense Mistral.
        sparse_embedder: Embedder sparse BM25.

    Returns:
        Chunks avec embeddings dense et sparse remplis.
    """
    dense_task = dense_embedder.embed_chunks(chunks, use_enriched=True)
    sparse_task = sparse_embedder.embed_chunks(chunks)
    result, _ = await asyncio.gather(dense_task, sparse_task)
    return result
