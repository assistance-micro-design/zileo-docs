"""Models pour les documents PDF et leur analyse."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class PageType(str, Enum):
    """Classification du type de page."""

    TEXT_ONLY = "text_only"
    HAS_TABLES = "has_tables"
    HAS_IMAGES = "has_images"
    HAS_CHARTS = "has_charts"
    SCANNED = "scanned"
    MIXED = "mixed"


@dataclass
class DocumentMetadata:
    """Metadonnees du document PDF.

    Attributes:
        document_id: Identifiant unique du document.
        file_hash: Hash SHA-256 du fichier.
        filename: Nom du fichier original.
        file_size_bytes: Taille du fichier en octets.
    """

    # === Identifiants ===
    document_id: str
    file_hash: str
    filename: str
    file_size_bytes: int

    # === Metadonnees PDF ===
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: datetime | None = None
    modification_date: datetime | None = None

    # === Statistiques ===
    total_pages: int = 0
    total_images: int = 0
    total_tables: int = 0

    # === Timestamps ===
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None

    # === Classification ===
    document_type: str | None = None
    language: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "document_id": self.document_id,
            "file_hash": self.file_hash,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "modification_date": (
                self.modification_date.isoformat() if self.modification_date else None
            ),
            "total_pages": self.total_pages,
            "total_images": self.total_images,
            "total_tables": self.total_tables,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "document_type": self.document_type,
            "language": self.language,
        }


@dataclass
class PageAnalysis:
    """Analyse detaillee d'une page.

    Attributes:
        page_number: Numero de la page (1-indexed).
        page_type: Type de contenu detecte.
    """

    # === Identification ===
    page_number: int
    page_type: PageType

    # === Detection elements ===
    has_native_text: bool
    native_text_length: int

    has_images: bool
    image_count: int
    image_coverage_ratio: float

    has_tables: bool
    table_count: int

    has_charts: bool

    # === Dimensions ===
    width: float
    height: float
    rotation: int

    # === Decision extraction ===
    extraction_method: str  # "pymupdf" | "mistral_ocr"
    priority: int

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "page_number": self.page_number,
            "page_type": self.page_type.value,
            "has_native_text": self.has_native_text,
            "native_text_length": self.native_text_length,
            "has_images": self.has_images,
            "image_count": self.image_count,
            "image_coverage_ratio": self.image_coverage_ratio,
            "has_tables": self.has_tables,
            "table_count": self.table_count,
            "has_charts": self.has_charts,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "extraction_method": self.extraction_method,
            "priority": self.priority,
        }


@dataclass
class DocumentAnalysisResult:
    """Resultat complet de l'analyse d'un document.

    Attributes:
        metadata: Metadonnees du document.
        pages: Liste des analyses par page.
    """

    metadata: DocumentMetadata
    pages: list[PageAnalysis]

    # Plan d'extraction
    pages_for_local_extraction: list[int] = field(default_factory=list)
    pages_for_ocr: list[int] = field(default_factory=list)

    # Estimations
    estimated_tokens: int = 0
    estimated_ocr_cost: float = 0.0
    estimated_processing_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """Convertit en dictionnaire serializable JSON."""
        return {
            "metadata": self.metadata.to_dict(),
            "pages": [page.to_dict() for page in self.pages],
            "pages_for_local_extraction": self.pages_for_local_extraction,
            "pages_for_ocr": self.pages_for_ocr,
            "estimated_tokens": self.estimated_tokens,
            "estimated_ocr_cost": self.estimated_ocr_cost,
            "estimated_processing_time_seconds": self.estimated_processing_time_seconds,
        }
