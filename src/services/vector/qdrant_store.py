# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Stockage vectoriel avec Qdrant pour les chunks de documents.

Ce module gere le stockage, la recherche et la gestion des chunks
de documents (PDF, Excel, Word) dans une base de donnees vectorielle Qdrant.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    MatchValue,
    PayloadSchemaType,
    PayloadSelectorInclude,
    PointStruct,
    Range,
    VectorParams,
)

from src.core.config import settings
from src.models.chunk import DocumentChunk
from src.models.document import DocumentMetadata
from src.models.unified import UnifiedMetadata


if TYPE_CHECKING:
    from src.services.embedding.sparse_embedder import SparseEmbeddingData


logger = logging.getLogger(__name__)

# Tables de mapping pour _build_filter (approche table-driven)
_MATCH_FILTER_KEYS: tuple[str, ...] = (
    "document_id",
    "content_type",
    "section_title",
    "doc_filename",
)
_BOOL_FILTER_KEYS: tuple[str, ...] = ("has_table", "has_image", "has_equation")

# Index Qdrant par type (pour _create_indexes)
_KEYWORD_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("document_id", PayloadSchemaType.KEYWORD),
    ("chunk_id", PayloadSchemaType.KEYWORD),
    ("content_type", PayloadSchemaType.KEYWORD),
    ("section_title", PayloadSchemaType.KEYWORD),
    ("doc_filename", PayloadSchemaType.KEYWORD),
)
_INTEGER_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("start_page", PayloadSchemaType.INTEGER),
    ("end_page", PayloadSchemaType.INTEGER),
    ("token_count", PayloadSchemaType.INTEGER),
)
_BOOL_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("has_table", PayloadSchemaType.BOOL),
    ("has_image", PayloadSchemaType.BOOL),
    ("has_equation", PayloadSchemaType.BOOL),
)
_DATETIME_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    ("ingested_at", PayloadSchemaType.DATETIME),
)
_ALL_PAYLOAD_INDEXES: tuple[tuple[str, PayloadSchemaType], ...] = (
    _KEYWORD_INDEXES + _INTEGER_INDEXES + _BOOL_INDEXES + _DATETIME_INDEXES
)


def _sanitize_text(text: str | None) -> str:
    """Nettoie le texte des caracteres Unicode problematiques.

    Remplace les caracteres de remplacement et normalise les espaces.

    Args:
        text: Texte a nettoyer.

    Returns:
        Texte nettoye.
    """
    if not text:
        return ""

    # Remplacer le caractere de remplacement Unicode
    text = text.replace("\ufffd", "")

    # Normaliser les espaces multiples
    text = re.sub(r"\s+", " ", text)

    # Supprimer les caracteres de controle (sauf newlines et tabs)
    text = "".join(
        char
        for char in text
        if char in ("\n", "\t", "\r") or (ord(char) >= 32 and ord(char) != 127)
    )

    return text.strip()


class QdrantVectorStore:
    """Stockage vectoriel avec Qdrant.

    Cette classe gere toutes les operations de stockage vectoriel:
    - Creation et configuration de la collection
    - Stockage des chunks avec embeddings et metadata
    - Recherche semantique avec filtrage avance
    - Gestion du cycle de vie des documents

    Attributes:
        client: Client Qdrant pour les operations sur la base.
        collection_name: Nom de la collection utilisee.

    Example:
        >>> store = QdrantVectorStore()
        >>> await store.initialize()
        >>> result = await store.store_chunks(chunks, doc_metadata)
        >>> results = await store.search(query_embedding, top_k=5)
    """

    COLLECTION_NAME = "documents"
    VECTOR_SIZE = 1024  # Mistral embed dimension

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialise le client Qdrant.

        Args:
            host: Hostname du serveur Qdrant. Defaut depuis settings.
            port: Port du serveur Qdrant. Defaut depuis settings.
            api_key: Cle API pour authentification. Defaut depuis settings.
        """
        self.client = QdrantClient(
            host=host or settings.QDRANT_HOST,
            port=port or settings.QDRANT_PORT,
            api_key=api_key or settings.QDRANT_API_KEY,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialise la collection si elle n'existe pas.

        Cree la collection avec la configuration optimisee pour
        les embeddings Mistral et configure tous les index necessaires.

        Raises:
            Exception: Si la creation de la collection echoue.
        """
        collections = await asyncio.to_thread(self.client.get_collections)
        exists = any(c.name == self.COLLECTION_NAME for c in collections.collections)

        if not exists:
            logger.info("Creating Qdrant collection: %s", self.COLLECTION_NAME)
            await self._create_collection()

        # Toujours creer les indexes (idempotent dans Qdrant)
        await self._create_indexes()
        logger.info("Collection %s ready", self.COLLECTION_NAME)
        self._initialized = True

    async def _create_collection(self) -> None:
        """Cree la collection avec configuration optimisee.

        Configure les vecteurs, la quantization scalaire pour
        reduire la memoire, et les optimiseurs pour l'indexation.
        """
        await asyncio.to_thread(
            self.client.create_collection,
            collection_name=self.COLLECTION_NAME,
            vectors_config={
                "dense": VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                    on_disk=False,
                ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                ),
            ),
        )

    async def _create_indexes(self) -> None:
        """Cree les index payload et full-text pour filtrage performant."""
        for field_name, field_type in _ALL_PAYLOAD_INDEXES:
            await asyncio.to_thread(
                self.client.create_payload_index,
                collection_name=self.COLLECTION_NAME,
                field_name=field_name,
                field_schema=field_type,
            )

        # TEXT index conserve pour le filtre text_search (MatchText dans _build_filter)
        # La recherche hybride utilise les sparse vectors BM25, pas ce TEXT index
        from qdrant_client.models import TextIndexParams, TokenizerType  # noqa: PLC0415

        await asyncio.to_thread(
            self.client.create_payload_index,
            collection_name=self.COLLECTION_NAME,
            field_name="content",
            field_schema=TextIndexParams(
                type="text",
                tokenizer=TokenizerType.WORD,
                min_token_len=2,
                max_token_len=20,
                lowercase=True,
            ),
        )

    async def store_chunks(
        self,
        chunks: list[DocumentChunk],
        document_metadata: DocumentMetadata,
    ) -> dict[str, Any]:
        """Stocke les chunks avec embeddings et metadata.

        Args:
            chunks: Liste des chunks a stocker (avec embeddings).
            document_metadata: Metadata du document parent.

        Returns:
            Dictionnaire avec statistiques de stockage:
            - stored_chunks: Nombre de chunks stockes
            - skipped_chunks: Nombre de chunks sans embedding
            - document_id: ID du document
            - collection: Nom de la collection

        Example:
            >>> result = await store.store_chunks(chunks, doc_meta)
            >>> print(f"Stored {result['stored_chunks']} chunks")
        """

        def payload_builder(chunk: DocumentChunk) -> dict[str, Any]:
            return self._build_payload(chunk, document_metadata)

        return await self._store_chunks_internal(
            chunks, document_metadata.document_id, payload_builder
        )

    async def store_unified_chunks(
        self,
        chunks: list[DocumentChunk],
        unified_metadata: UnifiedMetadata,
    ) -> dict[str, Any]:
        """Stocke les chunks avec embeddings et metadata unifiée (Excel/Word).

        Args:
            chunks: Liste des chunks a stocker (avec embeddings).
            unified_metadata: Metadata unifiée du document parent.

        Returns:
            Dictionnaire avec statistiques de stockage:
            - stored_chunks: Nombre de chunks stockes
            - skipped_chunks: Nombre de chunks sans embedding
            - document_id: ID du document
            - collection: Nom de la collection

        Example:
            >>> result = await store.store_unified_chunks(chunks, unified_meta)
            >>> print(f"Stored {result['stored_chunks']} chunks")
        """

        def payload_builder(chunk: DocumentChunk) -> dict[str, Any]:
            return self._build_unified_payload(chunk, unified_metadata)

        return await self._store_chunks_internal(
            chunks, unified_metadata.document_id, payload_builder
        )

    async def _store_chunks_internal(
        self,
        chunks: list[DocumentChunk],
        document_id: str,
        payload_builder: Callable[[DocumentChunk], dict[str, Any]],
    ) -> dict[str, Any]:
        """Pipeline commun de stockage : build points + upsert + stats."""
        points, skipped = self._build_points(chunks, payload_builder)
        await self._upsert_points(points)

        logger.info(
            "Stored %d chunks for document %s (skipped %d without embeddings)",
            len(points),
            document_id,
            skipped,
        )

        return {
            "stored_chunks": len(points),
            "skipped_chunks": skipped,
            "document_id": document_id,
            "collection": self.COLLECTION_NAME,
        }

    def _build_points(
        self,
        chunks: list[DocumentChunk],
        payload_builder: Callable[[DocumentChunk], dict[str, Any]],
    ) -> tuple[list[PointStruct], int]:
        """Construit les PointStruct a partir des chunks."""
        points: list[PointStruct] = []
        skipped = 0
        for chunk in chunks:
            if chunk.embedding is None or chunk.sparse_embedding is None:
                skipped += 1
                continue
            sparse = chunk.sparse_embedding
            points.append(
                PointStruct(
                    id=self._generate_point_id(chunk.metadata.chunk_id),
                    vector={
                        "dense": chunk.embedding,
                        "sparse": models.SparseVector(
                            indices=sparse.indices,
                            values=sparse.values,
                        ),
                    },
                    payload=payload_builder(chunk),
                )
            )
        return points, skipped

    async def _upsert_points(self, points: list[PointStruct]) -> None:
        """Upsert par batch de 20 points dans Qdrant."""
        batch_size = 20
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.COLLECTION_NAME,
                points=batch,
            )

    def _build_common_payload(self, chunk: DocumentChunk) -> dict[str, Any]:
        """Construit les champs communs du payload Qdrant.

        Args:
            chunk: Chunk a stocker.

        Returns:
            Dictionnaire partiel du payload (chunk + contenu + stats).
        """
        meta = chunk.metadata
        content = _sanitize_text(chunk.content)

        return {
            "chunk_id": meta.chunk_id,
            "document_id": meta.document_id,
            "parent_chunk_id": meta.parent_chunk_id or "",
            "content": content,
            "content_preview": content[:500] if content else "",
            "page_numbers": meta.page_numbers,
            "start_page": meta.start_page,
            "end_page": meta.end_page,
            "chunk_index": meta.chunk_index,
            "total_chunks": meta.total_chunks,
            "section_title": meta.section_title or "",
            "section_hierarchy": meta.section_hierarchy,
            "content_type": meta.content_type,
            "has_table": meta.has_table,
            "has_image": meta.has_image,
            "has_equation": meta.has_equation,
            "token_count": meta.token_count,
            "char_count": meta.char_count,
            "word_count": meta.word_count,
            "preceding_context": meta.preceding_context,
            "following_context": meta.following_context,
        }

    def _build_unified_payload(
        self,
        chunk: DocumentChunk,
        unified_meta: UnifiedMetadata,
    ) -> dict[str, Any]:
        """Construit le payload pour documents unifiés (Excel/Word)."""
        payload = self._build_common_payload(chunk)
        payload.update(
            {
                "document_type": unified_meta.document_type.value,
                "has_formula": unified_meta.has_formulas,
                "sheet_names": unified_meta.sheet_names,
                "doc_filename": unified_meta.filename,
                "doc_title": unified_meta.title or "",
                "doc_author": unified_meta.author or "",
                "doc_total_pages": unified_meta.page_count or 0,
                "doc_file_hash": unified_meta.file_hash,
                "ingested_at": unified_meta.indexed_at.isoformat(),
                "doc_creation_date": (
                    unified_meta.created_at.isoformat() if unified_meta.created_at else None
                ),
            }
        )
        return payload

    def _build_payload(
        self,
        chunk: DocumentChunk,
        doc_meta: DocumentMetadata,
    ) -> dict[str, Any]:
        """Construit le payload pour documents PDF."""
        payload = self._build_common_payload(chunk)
        payload.update(
            {
                "doc_filename": doc_meta.filename,
                "doc_title": doc_meta.title or "",
                "doc_author": doc_meta.author or "",
                "doc_total_pages": doc_meta.total_pages,
                "doc_file_hash": doc_meta.file_hash,
                "ingested_at": doc_meta.ingested_at.isoformat(),
                "doc_creation_date": (
                    doc_meta.creation_date.isoformat() if doc_meta.creation_date else None
                ),
            }
        )
        return payload

    def _generate_point_id(self, chunk_id: str) -> int:
        """Genere un ID numerique unique a partir du chunk_id.

        Utilise MD5 pour generer un hash reproductible qui permet
        l'upsert (mise a jour si existant).

        Args:
            chunk_id: Identifiant unique du chunk.

        Returns:
            Identifiant numerique positif pour Qdrant.
        """
        hash_bytes = hashlib.md5(chunk_id.encode()).hexdigest()[:16]
        return int(hash_bytes, 16)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Recherche semantique avec filtrage.

        Args:
            query_embedding: Vecteur de requete (1024 dimensions).
            top_k: Nombre maximum de resultats. Defaut 5.
            filters: Filtres optionnels (voir _build_filter).
            score_threshold: Score minimum de similarite. Defaut 0.7.

        Returns:
            Liste de dictionnaires avec les resultats:
            - chunk_id: ID du chunk
            - content: Contenu complet
            - content_preview: Apercu du contenu
            - score: Score de similarite
            - document_id: ID du document
            - page_numbers: Pages du chunk
            - section_title: Titre de section
            - content_type: Type de contenu
            - doc_filename: Nom du fichier

        Example:
            >>> results = await store.search(
            ...     query_embedding=embedding,
            ...     top_k=10,
            ...     filters={"document_id": "doc-123", "has_table": True},
            ... )
        """
        qdrant_filter = self._build_filter(filters) if filters else None

        response = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.COLLECTION_NAME,
            query=query_embedding,
            using="dense",
            limit=top_k,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return self._format_search_results(response.points)

    async def hybrid_search(
        self,
        query_embedding: list[float],
        sparse_embedding: SparseEmbeddingData,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Recherche hybride via Qdrant natif (prefetch + RRF fusion).

        Combine recherche dense (Mistral embeddings) et sparse (BM25)
        avec fusion RRF cote serveur Qdrant.

        Args:
            query_embedding: Vecteur dense (1024 dimensions Mistral).
            sparse_embedding: Donnees sparse BM25 (indices + values).
            top_k: Nombre maximum de resultats. Defaut 5.
            filters: Filtres optionnels (voir _build_filter).
            score_threshold: Score minimum (optionnel).

        Returns:
            Liste de resultats fusionnes par RRF, ordonnee par score.
        """
        qdrant_filter = self._build_filter(filters) if filters else None
        sparse_vec = models.SparseVector(
            indices=sparse_embedding.indices,
            values=sparse_embedding.values,
        )

        response = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=query_embedding,
                    using="dense",
                    limit=top_k * 2,
                ),
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse",
                    limit=top_k * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return self._format_search_results(response.points)

    def _format_search_results(self, points: list[Any]) -> list[dict[str, Any]]:
        """Transforme les points Qdrant en resultats de recherche."""
        return [
            {
                "chunk_id": hit.payload["chunk_id"] if hit.payload else None,
                "content": hit.payload["content"] if hit.payload else None,
                "content_preview": hit.payload.get("content_preview") if hit.payload else None,
                "score": getattr(hit, "score", 0.0),
                "document_id": hit.payload["document_id"] if hit.payload else None,
                "page_numbers": hit.payload.get("page_numbers", []) if hit.payload else [],
                "section_title": hit.payload.get("section_title") if hit.payload else None,
                "content_type": hit.payload.get("content_type") if hit.payload else None,
                "doc_filename": hit.payload.get("doc_filename") if hit.payload else None,
            }
            for hit in points
        ]

    def _build_filter(self, filters: dict[str, Any]) -> Filter | None:
        """Construit un filtre Qdrant a partir d'un dictionnaire.

        Args:
            filters: Dictionnaire des filtres supportes:
                - document_id: Filtre par ID document exact
                - content_type: Filtre par type de contenu
                - page_range: Tuple (start, end) pour pages
                - has_table: Boolean pour presence de tableaux
                - has_image: Boolean pour presence d'images
                - has_equation: Boolean pour presence d'equations
                - section_title: Filtre par titre de section
                - text_search: Recherche full-text dans content
                - doc_filename: Filtre par nom de fichier

        Returns:
            Filtre Qdrant ou None si aucune condition.
        """
        conditions: list[FieldCondition] = []
        conditions.extend(self._build_match_conditions(filters))
        conditions.extend(self._build_bool_conditions(filters))

        range_cond = self._build_range_condition(filters)
        if range_cond:
            conditions.append(range_cond)

        text_cond = self._build_text_search_condition(filters)
        if text_cond:
            conditions.append(text_cond)

        return Filter(must=conditions) if conditions else None

    def _build_match_conditions(self, filters: dict[str, Any]) -> list[FieldCondition]:
        """Construit les conditions MatchValue pour filtres keyword."""
        return [
            FieldCondition(key=key, match=MatchValue(value=filters[key]))
            for key in _MATCH_FILTER_KEYS
            if key in filters
        ]

    def _build_bool_conditions(self, filters: dict[str, Any]) -> list[FieldCondition]:
        """Construit les conditions booleennes (has_table, has_image, etc.)."""
        return [
            FieldCondition(key=key, match=MatchValue(value=True))
            for key in _BOOL_FILTER_KEYS
            if filters.get(key)
        ]

    def _build_range_condition(self, filters: dict[str, Any]) -> FieldCondition | None:
        """Construit la condition de filtre page_range."""
        if "page_range" not in filters:
            return None
        start, end = filters["page_range"]
        return FieldCondition(
            key="start_page",
            range=Range(gte=start, lte=end),
        )

    def _build_text_search_condition(self, filters: dict[str, Any]) -> FieldCondition | None:
        """Construit la condition de recherche full-text."""
        if "text_search" not in filters:
            return None
        return FieldCondition(
            key="content",
            match=MatchText(text=filters["text_search"]),
        )

    async def delete_document(self, document_id: str) -> int:
        """Supprime tous les chunks d'un document.

        Args:
            document_id: Identifiant du document a supprimer.

        Returns:
            Nombre de points supprimes (approximatif via status).

        Example:
            >>> count = await store.delete_document("doc-123")
            >>> print(f"Deleted chunks for document")
        """
        result = await asyncio.to_thread(
            self.client.delete,
            collection_name=self.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

        logger.info("Deleted chunks for document %s", document_id)

        # Retourne le status de l'operation
        # Note: Qdrant ne retourne pas le nombre exact de points supprimes
        return 1 if result.status else 0

    async def get_document_chunks(
        self,
        document_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Recupere tous les chunks d'un document.

        Args:
            document_id: Identifiant du document.
            limit: Nombre maximum de chunks a recuperer. Defaut 1000.

        Returns:
            Liste des payloads de tous les chunks du document.

        Example:
            >>> chunks = await store.get_document_chunks("doc-123")
            >>> for chunk in chunks:
            ...     print(chunk["content_preview"])
        """
        results, _ = await asyncio.to_thread(
            self.client.scroll,
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [point.payload for point in results if point.payload]

    async def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de la collection.

        Returns:
            Dictionnaire avec les statistiques:
            - points_count: Nombre total de points
            - indexed_vectors_count: Vecteurs indexes
            - status: Statut de la collection

        Example:
            >>> stats = await store.get_stats()
            >>> print(f"Total points: {stats['points_count']}")
        """
        info = await asyncio.to_thread(
            self.client.get_collection,
            self.COLLECTION_NAME,
        )

        return {
            "points_count": info.points_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": str(info.status),
        }

    async def list_documents(self) -> list[dict[str, Any]]:
        """Liste tous les documents indexes dans la collection.

        Recupere les documents uniques en scrollant la collection
        et en groupant par document_id.

        Returns:
            Liste de dictionnaires avec les infos de chaque document:
            - document_id: ID unique du document
            - filename: Nom du fichier
            - title: Titre du document
            - author: Auteur
            - total_pages: Nombre de pages
            - total_chunks: Nombre de chunks
            - ingested_at: Date d'ingestion

        Example:
            >>> docs = await store.list_documents()
            >>> for doc in docs:
            ...     print(f"{doc['filename']}: {doc['total_chunks']} chunks")
        """
        all_points = await self._scroll_all_points(
            payload_fields=[
                "document_id",
                "doc_filename",
                "doc_title",
                "doc_author",
                "doc_total_pages",
                "ingested_at",
            ],
        )
        return self._group_documents_from_points(all_points)

    async def _scroll_all_points(
        self,
        payload_fields: list[str],
        scroll_filter: Filter | None = None,
    ) -> list[Any]:
        """Scroll tous les points avec les champs payload demandes."""
        all_points: list[Any] = []
        offset = None

        while True:
            results, next_offset = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=100,
                offset=offset,
                with_payload=PayloadSelectorInclude(include=payload_fields),
                with_vectors=False,
            )
            all_points.extend(results)
            if next_offset is None:
                break
            offset = next_offset

        return all_points

    @staticmethod
    def _group_documents_from_points(points: list[Any]) -> list[dict[str, Any]]:
        """Regroupe les points par document_id avec comptage des chunks."""
        documents: dict[str, dict[str, Any]] = {}

        for point in points:
            if not point.payload:
                continue
            doc_id = point.payload.get("document_id")
            if not doc_id:
                continue
            if doc_id in documents:
                documents[doc_id]["total_chunks"] += 1
                continue
            documents[doc_id] = {
                "document_id": doc_id,
                "filename": point.payload.get("doc_filename", ""),
                "title": point.payload.get("doc_title", ""),
                "author": point.payload.get("doc_author", ""),
                "total_pages": point.payload.get("doc_total_pages", 0),
                "total_chunks": 1,
                "ingested_at": point.payload.get("ingested_at", ""),
            }

        return list(documents.values())

    async def find_document_by_filename(self, filename: str) -> dict[str, Any] | None:
        """Cherche un document deja indexe par son nom de fichier.

        Utilise l'index KEYWORD sur doc_filename pour une recherche performante.

        Args:
            filename: Nom du fichier (basename, ex: "rapport.pdf").

        Returns:
            Dictionnaire avec document_id, filename, total_chunks, ingested_at
            ou None si aucun document ne correspond.

        Example:
            >>> result = await store.find_document_by_filename("rapport.pdf")
            >>> if result:
            ...     print(f"Deja indexe: {result['document_id']}")
        """
        results, _next_offset = await asyncio.to_thread(
            self.client.scroll,
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="doc_filename",
                        match=MatchValue(value=filename),
                    ),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            return None

        point = results[0]
        if not point.payload:
            return None

        doc_id = point.payload.get("document_id", "")

        # Compter le nombre total de chunks pour ce document
        count_result = await asyncio.to_thread(
            self.client.count,
            collection_name=self.COLLECTION_NAME,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=doc_id),
                    ),
                ]
            ),
            exact=True,
        )

        return {
            "document_id": doc_id,
            "filename": filename,
            "total_chunks": count_result.count,
            "ingested_at": point.payload.get("ingested_at", ""),
            "file_hash": point.payload.get("doc_file_hash", ""),
        }
