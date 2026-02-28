# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Routes API pour la gestion des documents PDF."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.dependencies import OrchestratorDep, VectorStoreDep
from src.core.config import settings
from src.core.exceptions import (
    DocumentNotFoundError,
    PDFCorruptedError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    SourceFileNotFoundError,
)
from src.models.api import DeleteResult, ProcessingStatus


logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/index",
    summary="Extraire et indexer un PDF",
    description="Extrait le contenu d'un PDF et l'indexe dans la base vectorielle.",
)
@limiter.limit(settings.RATE_LIMIT_INDEX)  # type: ignore[untyped-decorator]
async def index_pdf(
    request: Request,
    orchestrator: OrchestratorDep,
    file: Annotated[UploadFile, File(description="Fichier PDF a traiter")],
    force_ocr: bool = False,
    table_format: str = "markdown",
) -> dict[str, Any]:
    """Extrait et indexe un fichier PDF.

    Pipeline complet:
    1. Extraction (native + OCR)
    2. Chunking semantique
    3. Generation d'embeddings
    4. Stockage dans Qdrant

    Args:
        orchestrator: Service d'orchestration injecte.
        file: Fichier PDF uploade.
        force_ocr: Forcer OCR sur toutes les pages.
        table_format: Format des tableaux (markdown/html).

    Returns:
        Resultat de l'indexation avec statistiques.

    Raises:
        HTTPException: Si le fichier est invalide.
    """
    # Validation du fichier
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit etre un PDF",
        )

    # Verifier la taille
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.MAX_PDF_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux: {size_mb:.1f}MB (max: {settings.MAX_PDF_SIZE_MB}MB)",
        )

    # Sauvegarder temporairement
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Initialiser l'orchestrateur et traiter
        await orchestrator.initialize()

        result = await orchestrator.process_and_index(
            tmp_path,
            options={
                "force_ocr": force_ocr,
                "table_format": table_format,
                "original_filename": file.filename,
            },
        )

        return {
            "status": ProcessingStatus.COMPLETED.value,
            "document_id": result.analysis.metadata.document_id,
            "filename": file.filename,
            "total_pages": result.analysis.metadata.total_pages,
            "pages_processed_native": result.pages_processed_native,
            "pages_processed_ocr": result.pages_processed_ocr,
            "chunks_generated": result.chunks_generated,
            "chunks_embedded": result.chunks_embedded,
            "chunks_stored": result.chunks_stored,
            "processing_time_seconds": result.processing_time_seconds,
            "errors": result.errors,
        }

    except SourceFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e
    except PDFCorruptedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e
    except (PDFTooLargeError, PDFTooManyPagesError) as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=e.message,
        ) from e
    finally:
        # Nettoyer le fichier temporaire
        tmp_path.unlink(missing_ok=True)


@router.get(
    "/{document_id}",
    summary="Obtenir les informations d'un document",
    description="Retourne les informations et chunks d'un document indexe.",
)
async def get_document(
    document_id: str,
    vector_store: VectorStoreDep,
) -> dict[str, Any]:
    """Recupere les informations d'un document indexe.

    Args:
        document_id: Identifiant du document.
        vector_store: Service de stockage vectoriel injecte.

    Returns:
        Informations du document avec ses chunks.

    Raises:
        HTTPException: Si le document n'existe pas.
    """
    try:
        chunks = await vector_store.get_document_chunks(document_id)

        if not chunks:
            raise DocumentNotFoundError(document_id)

        # Extraire les metadonnees du premier chunk
        first_chunk = chunks[0]

        return {
            "document_id": document_id,
            "filename": first_chunk.get("doc_filename"),
            "title": first_chunk.get("doc_title"),
            "author": first_chunk.get("doc_author"),
            "total_pages": first_chunk.get("doc_total_pages"),
            "total_chunks": len(chunks),
            "ingested_at": first_chunk.get("ingested_at"),
            "chunks": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "content_preview": c.get("content_preview"),
                    "page_numbers": c.get("page_numbers"),
                    "section_title": c.get("section_title"),
                    "content_type": c.get("content_type"),
                }
                for c in chunks
            ],
        }

    except DocumentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e


@router.delete(
    "/{document_id}",
    response_model=DeleteResult,
    summary="Supprimer un document",
    description="Supprime un document et tous ses chunks de l'index.",
)
async def delete_document(
    document_id: str,
    vector_store: VectorStoreDep,
) -> DeleteResult:
    """Supprime un document de l'index vectoriel.

    Args:
        document_id: Identifiant du document a supprimer.
        vector_store: Service de stockage vectoriel injecte.

    Returns:
        Resultat de la suppression.
    """
    result = await vector_store.delete_document(document_id)

    return DeleteResult(
        document_id=document_id,
        chunks_deleted=result,
        status="deleted" if result else "not_found",
    )


@router.get(
    "",
    summary="Lister les statistiques",
    description="Retourne les statistiques de la collection de documents.",
)
async def list_stats(
    vector_store: VectorStoreDep,
) -> dict[str, Any]:
    """Retourne les statistiques de la collection.

    Args:
        vector_store: Service de stockage vectoriel injecte.

    Returns:
        Statistiques de la collection.
    """
    try:
        stats = await vector_store.get_stats()
        return {
            "collection": vector_store.COLLECTION_NAME,
            "total_chunks": stats.get("points_count", 0),
            "indexed_vectors": stats.get("indexed_vectors_count", 0),
            "status": stats.get("status", "unknown"),
        }
    except Exception as e:
        logger.warning("Failed to get stats: %s", e)
        return {
            "collection": vector_store.COLLECTION_NAME,
            "total_chunks": 0,
            "indexed_vectors": 0,
            "status": "unavailable",
        }
