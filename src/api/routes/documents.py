# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Routes API pour la gestion des documents PDF."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi import Path as PathParam
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.auth import verify_api_key
from src.api.dependencies import OrchestratorDep, VectorStoreDep
from src.core.config import settings
from src.core.exceptions import (
    DocumentNotFoundError,
    PDFCorruptedError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    SourceFileNotFoundError,
)
from src.core.file_validation import validate_file_magic, validate_filename_safety
from src.models.api import DeleteResult, ProcessingStatus
from src.services.vector.payload_reader import extract_doc_summary


_UPLOAD_CHUNK_BYTES = 64 * 1024


logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/documents", tags=["Documents"], dependencies=[Depends(verify_api_key)])


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
    _validate_upload_filename(file.filename)
    tmp_path = await _stream_upload_to_temp(file, settings.MAX_FILE_SIZE_MB)

    try:
        if not validate_file_magic(tmp_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier invalide: magic number PDF manquant (%PDF-)",
            )

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

    except (
        SourceFileNotFoundError,
        PDFCorruptedError,
        PDFTooLargeError,
        PDFTooManyPagesError,
    ) as e:
        raise _orchestrator_error_to_http(e) from e
    finally:
        tmp_path.unlink(missing_ok=True)


def _validate_upload_filename(filename: str | None) -> None:
    """Verifie l'extension .pdf et l'absence de path traversal."""
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit etre un PDF",
        )
    if not validate_filename_safety(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom de fichier invalide (path traversal)",
        )


async def _stream_upload_to_temp(file: UploadFile, max_size_mb: int) -> Path:
    """Streame l'upload dans un fichier temporaire avec cap de taille (fail-fast).

    Args:
        file: Upload FastAPI.
        max_size_mb: Taille max autorisee en MB.

    Returns:
        Chemin du fichier temporaire ecrit.

    Raises:
        HTTPException 413: Si la taille depasse `max_size_mb`.
    """
    max_bytes = max_size_mb * 1024 * 1024
    written = 0
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
            written += len(chunk)
            if written > max_bytes:
                tmp.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Fichier trop volumineux (max: {max_size_mb}MB)",
                )
            tmp.write(chunk)
    return tmp_path


def _orchestrator_error_to_http(exc: Exception) -> HTTPException:
    """Mappe une erreur d'orchestration sur un code HTTP.

    Les erreurs metier connues (4xx) exposent leur message clair au client.
    Les autres exceptions sont loggees cote serveur et le client recoit
    un message generique (L5.a audit 2026-05-15: pas de leak d'internal state).

    Args:
        exc: Exception levee par l'orchestrateur.

    Returns:
        HTTPException avec le code adequat.
    """
    if isinstance(exc, SourceFileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, (PDFTooLargeError, PDFTooManyPagesError)):
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=exc.message
        )
    if isinstance(exc, PDFCorruptedError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    logger.exception("Unhandled orchestrator error", exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


@router.get(
    "/{document_id}",
    summary="Obtenir les informations d'un document",
    description="Retourne les informations et chunks d'un document indexe.",
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)  # type: ignore[untyped-decorator]
async def get_document(
    request: Request,
    document_id: Annotated[str, PathParam(min_length=1, max_length=255, pattern=r"^[\w\-]+$")],
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

        summary = extract_doc_summary(chunks[0])

        return {
            "document_id": document_id,
            "filename": summary["filename"],
            "title": summary["title"],
            "author": summary["author"],
            "total_pages": summary["total_pages"],
            "total_chunks": len(chunks),
            "ingested_at": summary["ingested_at"],
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
@limiter.limit(settings.RATE_LIMIT_DEFAULT)  # type: ignore[untyped-decorator]
async def delete_document(
    request: Request,
    document_id: Annotated[str, PathParam(min_length=1, max_length=255, pattern=r"^[\w\-]+$")],
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
@limiter.limit(settings.RATE_LIMIT_DEFAULT)  # type: ignore[untyped-decorator]
async def list_stats(
    request: Request,
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
