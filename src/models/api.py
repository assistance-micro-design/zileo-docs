"""Models pour les requetes et reponses API REST."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, Field


if TYPE_CHECKING:
    from datetime import datetime


# === Enums ===


class ProcessingStatus(str, Enum):
    """Statut de traitement d'un document."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


class TableFormat(str, Enum):
    """Format de sortie des tableaux."""

    MARKDOWN = "markdown"
    HTML = "html"


# === Request Models ===


class ExtractPDFRequest(BaseModel):
    """Requete d'extraction PDF.

    Attributes:
        file_path: Chemin vers le fichier PDF.
        force_ocr: Forcer OCR sur toutes les pages.
        table_format: Format des tableaux extraits.
        include_images: Inclure descriptions des images.
    """

    file_path: str | None = Field(
        default=None,
        description="Chemin vers le fichier PDF",
    )
    force_ocr: bool = Field(
        default=False,
        description="Forcer OCR sur toutes les pages",
    )
    table_format: TableFormat = Field(
        default=TableFormat.MARKDOWN,
        description="Format des tableaux",
    )
    include_images: bool = Field(
        default=True,
        description="Inclure descriptions des images",
    )


class IndexDocumentRequest(BaseModel):
    """Requete d'indexation d'un document.

    Attributes:
        document_id: Identifiant du document a indexer.
        collection_name: Nom de la collection Qdrant.
    """

    document_id: str
    collection_name: str = "pdf_documents"


class DeleteDocumentRequest(BaseModel):
    """Requete de suppression d'un document.

    Attributes:
        document_id: Identifiant du document a supprimer.
    """

    document_id: str


# === Response Models ===


class DocumentSummary(BaseModel):
    """Resume d'un document indexe.

    Attributes:
        document_id: Identifiant unique.
        filename: Nom du fichier.
        title: Titre du document.
        author: Auteur du document.
        total_pages: Nombre total de pages.
        total_chunks: Nombre de chunks generes.
        ingested_at: Date d'ingestion.
    """

    document_id: str
    filename: str
    title: str | None
    author: str | None
    total_pages: int
    total_chunks: int
    ingested_at: datetime


class ExtractionResult(BaseModel):
    """Resultat d'extraction d'un document.

    Attributes:
        document_id: Identifiant du document.
        status: Statut du traitement.
        metadata: Metadonnees extraites.
    """

    document_id: str
    status: ProcessingStatus
    metadata: dict[str, Any]

    # Statistiques
    total_pages: int
    pages_extracted_native: int
    pages_extracted_ocr: int
    total_chunks: int
    total_tokens: int

    # Couts
    ocr_cost: float

    # Timing
    processing_time_seconds: float


class IndexResult(BaseModel):
    """Resultat d'indexation d'un document.

    Attributes:
        document_id: Identifiant du document.
        chunks_indexed: Nombre de chunks indexes.
        collection: Nom de la collection.
        status: Statut de l'indexation.
    """

    document_id: str
    chunks_indexed: int
    collection: str
    status: str


class DeleteResult(BaseModel):
    """Resultat de suppression d'un document.

    Attributes:
        document_id: Identifiant du document.
        chunks_deleted: Nombre de chunks supprimes.
        status: Statut de la suppression.
    """

    document_id: str
    chunks_deleted: int
    status: str


class DocumentInfo(BaseModel):
    """Information complete sur un document.

    Attributes:
        document_id: Identifiant unique.
        filename: Nom du fichier.
        file_hash: Hash SHA-256.
        file_size_bytes: Taille en octets.
    """

    document_id: str
    filename: str
    file_hash: str
    file_size_bytes: int

    # Metadata PDF
    title: str | None
    author: str | None
    subject: str | None
    creation_date: datetime | None

    # Stats
    total_pages: int
    total_images: int
    total_tables: int
    total_chunks: int

    # Timestamps
    ingested_at: datetime
    processed_at: datetime | None

    # Pages detail
    pages_summary: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Reponse du health check.

    Attributes:
        status: Statut general ("healthy" | "degraded" | "unhealthy").
        version: Version de l'application.
        qdrant_status: Statut de la connexion Qdrant.
        mistral_status: Statut de la connexion Mistral API.
    """

    status: str
    version: str
    qdrant_status: str
    mistral_status: str


class ErrorResponse(BaseModel):
    """Reponse d'erreur standardisee.

    Attributes:
        error: Code d'erreur.
        detail: Message d'erreur detaille.
        code: Code technique de l'erreur.
    """

    error: str
    detail: str | None
    code: str


# === MCP Tool Schemas ===


class ExtractPDFParams(BaseModel):
    """Parametres du tool MCP index_document (extraction + indexation).

    Attributes:
        file_path: Chemin absolu vers le fichier PDF.
        force_ocr: Forcer OCR meme si le PDF contient du texte.
        table_format: Format des tableaux extraits.
    """

    file_path: Annotated[str, Field(description="Chemin absolu vers le PDF. Ex: /data/docs/rapport.pdf")]
    force_ocr: bool = Field(
        default=False,
        description="Forcer OCR meme si le PDF contient du texte",
    )
    table_format: str = Field(
        default="markdown",
        description="Format des tableaux extraits: markdown ou html",
    )


class IndexDocumentParams(BaseModel):
    """Parametres du tool MCP index_document.

    Attributes:
        document_id: ID du document a indexer.
        collection_name: Nom de la collection Qdrant.
    """

    document_id: Annotated[str, Field(description="ID du document a indexer")]
    collection_name: str = Field(
        default="pdf_documents",
        description="Nom de la collection Qdrant",
    )


class SearchDocumentsParams(BaseModel):
    """Parametres du tool MCP search_documents.

    Attributes:
        query: Requete de recherche.
        top_k: Nombre de resultats.
        filters: Filtres optionnels.
    """

    query: Annotated[str, Field(description="Requete de recherche")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100, description="Nombre de resultats")]
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filtres optionnels",
    )


class GetDocumentParams(BaseModel):
    """Parametres du tool MCP get_document_info.

    Attributes:
        document_id: ID du document.
    """

    document_id: Annotated[str, Field(description="ID du document")]


class DeleteDocumentParams(BaseModel):
    """Parametres du tool MCP delete_document.

    Attributes:
        document_id: ID du document a supprimer de l'index.
    """

    document_id: Annotated[str, Field(description="ID du document a supprimer")]
