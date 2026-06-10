# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Models pour les requetes et reponses API REST."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.file_validation import validate_filename_safety
from src.models.excel_edit import EditOp
from src.models.excel_generation import SheetDef


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


# === Response Models ===


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


# === MCP Tool Schemas ===


class SearchHybridParams(BaseModel):
    """Parametres du tool MCP search_hybrid (recherche dense + BM25 + RRF).

    Attributes:
        query: Requete de recherche.
        top_k: Nombre de resultats.
        filters: Filtres optionnels.
        min_cosine_relevance: Garde-fou cosinus anti hors-domaine.
    """

    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=2000, description="Requete de recherche")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100, description="Nombre de resultats")]
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filtres optionnels",
    )
    min_cosine_relevance: Annotated[
        float | None,
        Field(
            default=None,
            ge=0.0,
            le=1.0,
            description=(
                "Garde-fou cosinus (opt-in, 0.0-1.0). Si le top-1 en similarite cosinus "
                "dense ne depasse pas ce seuil, retourne liste vide. Evite les faux positifs "
                "hors-domaine (calibre empirique: 0.72)."
            ),
        ),
    ]


class SearchSemanticParams(BaseModel):
    """Parametres du tool MCP search_semantic (cosinus pur).

    Attributes:
        query: Requete de recherche.
        top_k: Nombre de resultats.
        filters: Filtres optionnels.
        score_threshold: Seuil de similarite cosinus (defaut 0.7).
    """

    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=2000, description="Requete de recherche")]
    top_k: Annotated[int, Field(default=5, ge=1, le=100, description="Nombre de resultats")]
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filtres optionnels",
    )
    score_threshold: Annotated[
        float,
        Field(
            default=0.7,
            ge=0.0,
            le=1.0,
            description=(
                "Seuil de similarite cosinus (0.0-1.0, defaut 0.7). Les chunks dont le score "
                "ne depasse pas ce seuil sont filtres."
            ),
        ),
    ]


class GetDocumentParams(BaseModel):
    """Parametres du tool MCP get_document_info.

    Attributes:
        document_id: ID du document.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: Annotated[str, Field(description="ID du document")]


class DeleteDocumentParams(BaseModel):
    """Parametres du tool MCP delete_document.

    Attributes:
        document_id: ID du document a supprimer de l'index.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: Annotated[str, Field(description="ID du document a supprimer")]


class ReadDocumentContentParams(BaseModel):
    """Parametres du tool MCP read_document_content.

    Attributes:
        document_id: ID du document indexe.
        page_start: Page de debut (1-indexed, inclus).
        page_end: Page de fin (1-indexed, inclus).
        include_chunks_detail: Inclure metadonnees par chunk.
    """

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
    table_format: Literal["markdown", "html"] = Field(
        default="markdown",
        description="Format des tableaux extraits: markdown ou html",
    )


class GetExcelFormulasParams(BaseModel):
    """Paramètres du tool MCP get_excel_formulas.

    Attributes:
        document_id: ID du document Excel indexé.
        sheet: Filtrer par nom de feuille.
        cell_range: Filtrer par plage de cellules.
    """

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
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
        },
    )

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

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
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
        },
    )

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


class CreateWordParams(BaseModel):
    """Parametres du tool MCP create_word_document.

    Attributes:
        filename: Nom du fichier docx a creer.
        content: Contenu Markdown a convertir en Word.
        title: Titre du document (metadonnee).
        author: Auteur du document (metadonnee).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "filename": "report.docx",
                    "content": "# Report\n\n## Introduction\n\nThis is a **bold** statement.\n\n- Item 1\n- Item 2\n  - Sub-item\n\n| Name | Value |\n|------|-------|\n| A | 1 |\n",
                    "title": "Monthly Report",
                    "author": "Zileo",
                }
            ]
        },
    )

    filename: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            pattern=r"^[\w\-. ()]+\.docx$",
            description="Nom du fichier. Doit se terminer par .docx",
        ),
    ]
    content: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500_000,
            description="Contenu Markdown a convertir en document Word",
        ),
    ]
    title: Annotated[str | None, Field(default=None, max_length=255)] = None
    author: Annotated[str | None, Field(default=None, max_length=255)] = None


class CreateWordResult(BaseModel):
    """Resultat de la creation d'un document Word.

    Attributes:
        file_path: Chemin absolu du fichier cree.
        filename: Nom du fichier.
        file_size_bytes: Taille du fichier en octets.
        overwritten: True si un fichier existant a ete ecrase.
    """

    file_path: str
    filename: str
    file_size_bytes: int
    overwritten: bool = False


class ListAvailableDocumentsParams(BaseModel):
    """Paramètres du tool MCP list_available_documents.

    Attributes:
        source: Source des fichiers a lister.
        type_filter: Filtrer par type de document.
        subdirectory: Sous-dossier à explorer.
        recursive: Explorer récursivement.
    """

    model_config = ConfigDict(extra="forbid")

    source: Annotated[
        str,
        Field(default="documents", description="Source des fichiers a lister"),
    ] = "documents"
    type_filter: str = Field(
        default="all",
        description="Filtrer par type: pdf, excel, word, all",
    )
    subdirectory: str = Field(
        default="",
        description="Sous-dossier relatif à explorer",
    )
    recursive: bool = Field(
        default=True,
        description="Explorer récursivement les sous-dossiers",
    )

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Valide que la source est une valeur connue."""
        valid = {"documents", "generated"}
        if v not in valid:
            msg = f"source invalide: '{v}'. Valeurs possibles: {', '.join(sorted(valid))}"
            raise ValueError(msg)
        return v

    @field_validator("type_filter")
    @classmethod
    def validate_type_filter(cls, v: str) -> str:
        """Valide que le type_filter est une valeur connue."""
        all_valid = {"all", "pdf", "excel", "word"}
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

    model_config = ConfigDict(extra="forbid")

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
        if not validate_filename_safety(v):
            msg = "Le nom de fichier ne doit pas contenir '..' , '/' ou '\\'"
            raise ValueError(msg)
        return v
