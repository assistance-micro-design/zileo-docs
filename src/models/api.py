# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Models pour les requetes et reponses API REST."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, Field, field_validator

from src.models.excel_edit import EditOp
from src.models.excel_generation import SheetDef
from src.models.presentation_edit import PresentationEditOp
from src.models.presentation_generation import SlideDef


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
    collection_name: str = "documents"


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

    file_path: Annotated[
        str, Field(description="Chemin absolu vers le PDF. Ex: /data/docs/rapport.pdf")
    ]
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
        default="documents",
        description="Nom de la collection Qdrant",
    )


class SearchDocumentsParams(BaseModel):
    """Parametres du tool MCP search_documents.

    Attributes:
        query: Requete de recherche.
        top_k: Nombre de resultats.
        score_threshold: Score minimum de similarite.
        filters: Filtres optionnels.
    """

    query: Annotated[str, Field(description="Requete de recherche")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100, description="Nombre de resultats")]
    score_threshold: Annotated[
        float, Field(default=0.7, ge=0.0, le=1.0, description="Score minimum de similarite")
    ]
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


class ReadDocumentContentParams(BaseModel):
    """Parametres du tool MCP read_document_content.

    Attributes:
        document_id: ID du document indexe.
        page_start: Page de debut (1-indexed, inclus).
        page_end: Page de fin (1-indexed, inclus).
        include_chunks_detail: Inclure metadonnees par chunk.
    """

    document_id: Annotated[
        str,
        Field(description="ID du document (retourne par index_document ou list_indexed_documents)"),
    ]
    page_start: int | None = Field(
        default=None,
        ge=1,
        description="Page de debut (1-indexed). Si omis, commence au debut.",
    )
    page_end: int | None = Field(
        default=None,
        ge=1,
        description="Page de fin (1-indexed). Si omis, va jusqu'a la fin.",
    )
    include_chunks_detail: bool = Field(
        default=False,
        description="Inclure les metadonnees detaillees de chaque chunk.",
    )


class UnifiedIndexDocumentParams(BaseModel):
    """Paramètres du tool MCP index_document (unifié PDF/Excel/Word).

    Attributes:
        file_path: Chemin absolu vers le fichier.
        force_ocr: PDF uniquement: forcer OCR même si texte natif.
        sheets: Excel uniquement: noms des feuilles à indexer.
        table_format: Format de sortie des tableaux.
    """

    file_path: Annotated[
        str, Field(description="Chemin absolu vers le document. Ex: /data/docs/rapport.xlsx")
    ]
    force_ocr: bool = Field(
        default=False,
        description="PDF uniquement: forcer OCR même si le document contient du texte",
    )
    sheets: list[str] | None = Field(
        default=None,
        description="Excel uniquement: noms des feuilles à indexer (toutes si vide)",
    )
    table_format: str = Field(
        default="markdown",
        description="Format des tableaux extraits: markdown, html ou json",
    )


class UnifiedIndexDocumentResult(BaseModel):
    """Résultat de l'indexation d'un document unifié.

    Attributes:
        document_id: Identifiant unique du document indexé.
        document_type: Type de document (pdf, excel, word).
        filename: Nom du fichier.
        chunks_stored: Nombre de chunks indexés.
        has_tables: Document contient des tableaux.
        has_formulas: Document contient des formules (Excel).
        has_images: Document contient des images.
        sheet_names: Noms des feuilles (Excel uniquement).
    """

    document_id: str
    document_type: str
    filename: str
    chunks_stored: int
    has_tables: bool = False
    has_formulas: bool = False
    has_images: bool = False
    sheet_names: list[str] | None = None
    processing_time_seconds: float | None = None


class GetExcelFormulasParams(BaseModel):
    """Paramètres du tool MCP get_excel_formulas.

    Attributes:
        document_id: ID du document Excel indexé.
        sheet: Filtrer par nom de feuille.
        cell_range: Filtrer par plage de cellules.
    """

    document_id: Annotated[
        str, Field(description="ID du document Excel (retourné par index_document)")
    ]
    sheet: str | None = Field(
        default=None,
        description="Filtrer par nom de feuille",
    )
    cell_range: str | None = Field(
        default=None,
        description="Filtrer par plage de cellules. Ex: 'A1:D10'",
    )


class CreateExcelParams(BaseModel):
    """Parametres du tool MCP create_excel_document.

    Attributes:
        filename: Nom du fichier xlsx a creer.
        sheets: Definitions des feuilles.
        author: Auteur du classeur (metadonnee).
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "filename": "report.xlsx",
                    "sheets": [
                        {
                            "name": "Data",
                            "headers": ["Name", "Value"],
                            "rows": [["Item A", 100], ["Item B", 200]],
                            "charts": [
                                {
                                    "type": "bar",
                                    "data_range": "B1:B3",
                                    "categories_range": "A2:A3",
                                    "title": "Values",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[\w\-. ()]+\.xlsx$",
            description="Nom du fichier. Doit se terminer par .xlsx",
        ),
    ]
    sheets: Annotated[list[SheetDef], Field(min_length=1, max_length=50)]
    author: Annotated[str | None, Field(default=None, max_length=255)] = None


class CreateExcelResult(BaseModel):
    """Resultat de la creation d'un document Excel.

    Attributes:
        file_path: Chemin absolu du fichier cree.
        filename: Nom du fichier.
        sheets_created: Nombre de feuilles creees.
        total_rows: Nombre total de lignes de donnees.
        total_charts: Nombre total de graphiques.
        file_size_bytes: Taille du fichier en octets.
        overwritten: True si un fichier existant a ete ecrase.
    """

    file_path: str
    filename: str
    sheets_created: int
    total_rows: int
    total_charts: int
    file_size_bytes: int
    overwritten: bool = False


class EditExcelParams(BaseModel):
    """Parametres du tool MCP edit_excel_document.

    Attributes:
        filename: Nom du fichier xlsx existant dans OUTPUT_PATH.
        operations: Liste ordonnee d'operations a appliquer.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "filename": "report.xlsx",
                    "operations": [
                        {
                            "op": "update_cells",
                            "sheet": "Sheet1",
                            "cells": {"A1": 42, "B1": "hello"},
                        },
                        {
                            "op": "add_chart",
                            "sheet": "Sheet1",
                            "chart": {"type": "bar", "data_range": "A1:B5", "title": "Sales"},
                        },
                        {"op": "delete_rows", "sheet": "Sheet1", "start_row": 10, "end_row": 12},
                    ],
                }
            ]
        }
    }

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[\w\-. ()]+\.xlsx$",
            description="Nom du fichier existant dans OUTPUT_PATH. Doit se terminer par .xlsx",
        ),
    ]
    operations: Annotated[
        list[EditOp],
        Field(min_length=1, max_length=100, description="Operations a appliquer (en ordre)"),
    ]


class EditExcelResult(BaseModel):
    """Resultat de l'edition d'un document Excel.

    Attributes:
        file_path: Chemin absolu du fichier edite.
        filename: Nom du fichier.
        operations_applied: Nombre d'operations appliquees avec succes.
        operations_skipped: Nombre d'operations ignorees (degradation gracieuse).
        file_size_bytes: Taille du fichier en octets apres edition.
    """

    file_path: str
    filename: str
    operations_applied: int
    operations_skipped: int
    file_size_bytes: int


class CreatePresentationParams(BaseModel):
    """Parametres du tool MCP create_presentation.

    Attributes:
        filename: Nom du fichier pptx a creer.
        slides: Definitions des slides.
        author: Auteur de la presentation (metadonnee).
        template: Nom du fichier template .pptx (optionnel).
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "filename": "presentation.pptx",
                    "slides": [
                        {
                            "layout": "title_slide",
                            "title": "Ma Presentation",
                            "subtitle": "Par l'equipe",
                        },
                        {
                            "layout": "content_bullets",
                            "title": "Points cles",
                            "bullets": [
                                {"text": "Premier point"},
                                {"text": "Deuxieme point"},
                            ],
                        },
                    ],
                }
            ]
        }
    }

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[\w\-. ()]+\.pptx$",
            description="Nom du fichier. Doit se terminer par .pptx",
        ),
    ]
    slides: Annotated[list[SlideDef], Field(min_length=1, max_length=100)]
    author: Annotated[str | None, Field(default=None, max_length=255)] = None
    template: Annotated[
        str | None,
        Field(
            default=None,
            max_length=255,
            description="Nom du fichier template .pptx dans le dossier templates",
        ),
    ] = None


class CreatePresentationResult(BaseModel):
    """Resultat de la creation d'une presentation PowerPoint.

    Attributes:
        file_path: Chemin absolu du fichier cree.
        filename: Nom du fichier.
        slides_created: Nombre de slides crees.
        total_images: Nombre total d'images inserees.
        total_charts: Nombre total de graphiques.
        file_size_bytes: Taille du fichier en octets.
        overwritten: True si un fichier existant a ete ecrase.
    """

    file_path: str
    filename: str
    slides_created: int
    total_images: int
    total_charts: int
    file_size_bytes: int
    overwritten: bool = False


class EditPresentationParams(BaseModel):
    """Parametres du tool MCP edit_presentation.

    Attributes:
        filename: Nom du fichier pptx existant dans OUTPUT_PATH.
        operations: Liste ordonnee d'operations a appliquer.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "filename": "presentation.pptx",
                    "operations": [
                        {
                            "op": "update_title",
                            "slide_index": 0,
                            "title": "Nouveau titre",
                        },
                        {
                            "op": "add_slide",
                            "slide": {
                                "layout": "content_bullets",
                                "title": "Nouveau slide",
                                "bullets": [{"text": "Point"}],
                            },
                        },
                    ],
                }
            ]
        }
    }

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[\w\-. ()]+\.pptx$",
            description="Nom du fichier existant dans OUTPUT_PATH. Doit se terminer par .pptx",
        ),
    ]
    operations: Annotated[
        list[PresentationEditOp],
        Field(min_length=1, max_length=100, description="Operations a appliquer (en ordre)"),
    ]


class EditPresentationResult(BaseModel):
    """Resultat de l'edition d'une presentation PowerPoint.

    Attributes:
        file_path: Chemin absolu du fichier edite.
        filename: Nom du fichier.
        operations_applied: Nombre d'operations appliquees avec succes.
        operations_skipped: Nombre d'operations ignorees (degradation gracieuse).
        file_size_bytes: Taille du fichier en octets apres edition.
    """

    file_path: str
    filename: str
    operations_applied: int
    operations_skipped: int
    file_size_bytes: int


class ListAvailableDocumentsParams(BaseModel):
    """Paramètres du tool MCP list_available_documents.

    Attributes:
        source: Source des fichiers a lister.
        type_filter: Filtrer par type de document.
        subdirectory: Sous-dossier à explorer.
        recursive: Explorer récursivement.
    """

    source: Annotated[
        str,
        Field(default="documents", description="Source des fichiers a lister"),
    ] = "documents"
    type_filter: str = Field(
        default="all",
        description="Filtrer par type: pdf, excel, word, presentation, template, image, all",
    )
    subdirectory: str = Field(
        default="",
        description="Sous-dossier relatif à explorer",
    )
    recursive: bool = Field(
        default=True,
        description="Explorer récursivement les sous-dossiers",
    )

    _VALID_TYPES_BY_SOURCE: dict[str, set[str]] = {
        "documents": {"all", "pdf", "excel", "word"},
        "generated": {"all", "excel", "presentation"},
        "templates": {"all", "template"},
        "images": {"all", "image"},
    }

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Valide que la source est une valeur connue."""
        valid = {"documents", "generated", "templates", "images"}
        if v not in valid:
            msg = f"source invalide: '{v}'. Valeurs possibles: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return v

    @field_validator("type_filter")
    @classmethod
    def validate_type_filter(cls, v: str) -> str:
        """Valide que le type_filter est une valeur connue."""
        all_valid = {"all", "pdf", "excel", "word", "presentation", "template", "image"}
        if v not in all_valid:
            msg = f"type_filter invalide: '{v}'. Valeurs possibles: {', '.join(sorted(all_valid))}"
            raise ValueError(msg)
        return v


class InspectGeneratedFileParams(BaseModel):
    """Parametres du tool MCP inspect_generated_file.

    Attributes:
        filename: Nom du fichier dans OUTPUT_PATH.
        max_rows_per_sheet: Nombre max de lignes a afficher par feuille Excel.
    """

    filename: Annotated[
        str,
        Field(min_length=1, max_length=255, description="Nom du fichier dans OUTPUT_PATH"),
    ]
    max_rows_per_sheet: Annotated[
        int,
        Field(default=10, ge=1, le=100, description="Nombre max de lignes a afficher par feuille"),
    ] = 10

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Valide que le nom de fichier ne contient pas de traversal."""
        if ".." in v or "/" in v or "\\" in v:
            msg = "Le nom de fichier ne doit pas contenir '..' , '/' ou '\\'"
            raise ValueError(msg)
        return v
