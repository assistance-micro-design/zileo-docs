# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Service d'embedding avec Mistral Embed API.

Ce module fournit un service pour generer des embeddings vectoriels
a partir de texte en utilisant l'API Mistral Embed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import tiktoken
from mistralai import Mistral

from src.core.config import settings
from src.models.chunk import DocumentChunk


if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class MistralEmbedder:
    """Generation d'embeddings avec Mistral Embed.

    Cette classe gere la generation d'embeddings vectoriels pour des chunks
    de documents ou des requetes de recherche, en respectant les limites
    de l'API Mistral.

    Attributes:
        MODEL: Nom du modele d'embedding Mistral.
        DIMENSIONS: Nombre de dimensions des vecteurs generes.
        MAX_BATCH_SIZE: Nombre maximum de textes par requete.
        MAX_TOKENS_PER_REQUEST: Nombre maximum de tokens par requete.

    Example:
        >>> embedder = MistralEmbedder()
        >>> chunks = await embedder.embed_chunks(document_chunks)
        >>> query_embedding = await embedder.embed_query("recherche semantique")
    """

    MODEL: str = "mistral-embed"
    DIMENSIONS: int = 1024
    MAX_BATCH_SIZE: int = 100
    MAX_TOKENS_PER_REQUEST: int = 16000

    def __init__(self, api_key: str | None = None) -> None:
        """Initialise le service d'embedding Mistral.

        Args:
            api_key: Cle API Mistral. Si None, utilise la config globale.

        Raises:
            ValueError: Si aucune cle API n'est configuree.
        """
        resolved_api_key = api_key or settings.MISTRAL_API_KEY
        if not resolved_api_key:
            raise ValueError(
                "MISTRAL_API_KEY est requise pour le service d'embedding. "
                "Configurez-la via la variable d'environnement ou le parametre api_key."
            )

        self.client = Mistral(
            api_key=resolved_api_key,
            timeout_ms=settings.MISTRAL_TIMEOUT_S * 1000,
        )
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self._model = settings.MISTRAL_EMBED_MODEL or self.MODEL

        logger.debug(
            "MistralEmbedder initialise avec modele=%s, dimensions=%d",
            self._model,
            self.DIMENSIONS,
        )

    async def embed_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        use_enriched: bool = True,
    ) -> list[DocumentChunk]:
        """Genere des embeddings pour une liste de chunks.

        Traite les chunks par batches en respectant les limites de l'API
        Mistral (MAX_BATCH_SIZE et MAX_TOKENS_PER_REQUEST).

        Args:
            chunks: Liste des chunks a enrichir avec des embeddings.
            use_enriched: Si True, utilise content_with_context pour l'embedding.
                         Si False, utilise content brut.

        Returns:
            Liste des memes chunks avec le champ embedding rempli.

        Raises:
            ValueError: Si la liste de chunks est vide.
            MistralAPIError: En cas d'erreur de l'API Mistral.

        Example:
            >>> embedder = MistralEmbedder()
            >>> chunks = [DocumentChunk(content="texte", metadata=...)]
            >>> embedded_chunks = await embedder.embed_chunks(chunks)
            >>> assert embedded_chunks[0].embedding is not None
        """
        if not chunks:
            logger.warning("embed_chunks appele avec une liste vide")
            return []

        chunks_list = list(chunks)
        texts = self._prepare_texts(chunks_list, use_enriched)
        batches = self._create_batches(texts)

        logger.info(
            "Embedding de %d chunks en %d batches (use_enriched=%s)",
            len(chunks_list),
            len(batches),
            use_enriched,
        )

        all_embeddings: list[list[float]] = []
        for batch in batches:
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        for chunk, embedding in zip(chunks_list, all_embeddings, strict=True):
            chunk.embedding = embedding

        logger.info("Embedding termine: %d chunks", len(chunks_list))
        return chunks_list

    async def embed_query(self, query: str) -> list[float]:
        """Genere un embedding pour une requete de recherche.

        Args:
            query: Texte de la requete a transformer en vecteur.

        Returns:
            Vecteur d'embedding de dimension DIMENSIONS (1024).

        Raises:
            ValueError: Si la requete est vide.
            MistralAPIError: En cas d'erreur de l'API Mistral.

        Example:
            >>> embedder = MistralEmbedder()
            >>> embedding = await embedder.embed_query("comment configurer l'app?")
            >>> assert len(embedding) == 1024
        """
        if not query or not query.strip():
            raise ValueError("La requete ne peut pas etre vide")

        query = query.strip()
        token_count = len(self.tokenizer.encode(query))

        logger.debug(
            "Embedding requete: %d tokens, %d chars",
            token_count,
            len(query),
        )

        # Utiliser asyncio.to_thread pour ne pas bloquer l'event loop
        # car le client Mistral est synchrone
        response = await asyncio.to_thread(
            self.client.embeddings.create,
            model=self._model,
            inputs=[query],
        )

        embedding = list(response.data[0].embedding)

        logger.debug(
            "Embedding requete genere: %d dimensions",
            len(embedding),
        )

        return embedding

    def _prepare_texts(
        self,
        chunks: list[DocumentChunk],
        use_enriched: bool,
    ) -> list[str]:
        """Prepare les textes a embedder depuis les chunks.

        Args:
            chunks: Liste des chunks.
            use_enriched: Si True, utilise content_with_context.

        Returns:
            Liste des textes extraits des chunks.
        """
        texts: list[str] = []

        for chunk in chunks:
            text = (
                chunk.content_with_context
                if use_enriched and chunk.content_with_context
                else chunk.content
            )
            texts.append(text)

        return texts

    def _create_batches(self, texts: list[str]) -> list[list[str]]:
        """Cree des batches de textes respectant les limites de l'API.

        Les batches sont crees en respectant deux contraintes:
        - Maximum MAX_BATCH_SIZE textes par batch
        - Maximum MAX_TOKENS_PER_REQUEST tokens par batch

        Args:
            texts: Liste des textes a regrouper en batches.

        Returns:
            Liste de batches, chaque batch etant une liste de textes.

        Note:
            Si un texte individuel depasse MAX_TOKENS_PER_REQUEST,
            il sera place seul dans un batch (tronque si necessaire
            par l'API Mistral).
        """
        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0

        for text in texts:
            text_tokens = len(self.tokenizer.encode(text))

            # Verifier si on doit commencer un nouveau batch
            should_start_new_batch = len(current_batch) >= self.MAX_BATCH_SIZE or (
                current_batch and current_tokens + text_tokens > self.MAX_TOKENS_PER_REQUEST
            )

            if not should_start_new_batch:
                current_batch.append(text)
                current_tokens += text_tokens
                continue
            if current_batch:
                batches.append(current_batch)
            current_batch = [text]
            current_tokens = text_tokens

        # Ne pas oublier le dernier batch
        if current_batch:
            batches.append(current_batch)

        return batches

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Genere les embeddings pour un batch de textes.

        Args:
            texts: Liste des textes a embedder (doit respecter les limites).

        Returns:
            Liste des vecteurs d'embedding dans le meme ordre que les textes.

        Raises:
            MistralAPIError: En cas d'erreur de l'API.
        """
        if not texts:
            return []

        # Utiliser asyncio.to_thread pour ne pas bloquer l'event loop
        response = await asyncio.to_thread(
            self.client.embeddings.create,
            model=self._model,
            inputs=texts,
        )

        # Extraire les embeddings dans l'ordre
        return [list(item.embedding) for item in response.data]

    def count_tokens(self, text: str) -> int:
        """Compte le nombre de tokens dans un texte.

        Utilise le tokenizer cl100k_base pour un comptage precis
        compatible avec les modeles Mistral.

        Args:
            text: Texte dont on veut compter les tokens.

        Returns:
            Nombre de tokens.

        Example:
            >>> embedder = MistralEmbedder()
            >>> count = embedder.count_tokens("Hello world")
            >>> assert count == 2
        """
        return len(self.tokenizer.encode(text))

    @property
    def dimensions(self) -> int:
        """Retourne le nombre de dimensions des embeddings."""
        return self.DIMENSIONS

    @property
    def model_name(self) -> str:
        """Retourne le nom du modele d'embedding utilise."""
        return self._model
