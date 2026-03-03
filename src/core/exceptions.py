# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Exceptions personnalisees pour l'application."""

from __future__ import annotations

from typing import Any


class MCPZileoError(Exception):
    """Classe de base pour toutes les exceptions de l'application.

    Inclut un champ `suggestion` pour guider les LLM sur comment corriger l'erreur.
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        """Initialise l'exception.

        Args:
            message: Message d'erreur lisible.
            code: Code d'erreur unique pour identification.
            details: Details supplementaires optionnels.
            suggestion: Conseil pour le LLM sur comment corriger l'erreur.
            parameter: Nom du parametre concerne (pour les erreurs de validation).
            retry: True si le LLM peut reessayer avec des parametres corriges.
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.suggestion = suggestion
        self.parameter = parameter
        self.retry = retry

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'exception en dictionnaire serializable."""
        result: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.parameter:
            result["parameter"] = self.parameter
        if self.retry:
            result["retry"] = self.retry
        return result

    def to_llm_format(self) -> str:
        """Formate l'erreur pour le LLM de maniere actionnable."""
        lines = [f"ERROR [{self.code}]: {self.message}"]
        if self.suggestion:
            lines.append(f"SUGGESTION: {self.suggestion}")
        if self.parameter:
            lines.append(f"PARAMETER: {self.parameter}")
        if self.retry:
            lines.append("RETRY: Corriger et reessayer")
        return "\n".join(lines)


# === PDF Processing Errors ===


class PDFError(MCPZileoError):
    """Erreur liee au traitement PDF."""

    def __init__(
        self,
        message: str,
        code: str = "PDF_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class SourceFileNotFoundError(PDFError):
    """Fichier source introuvable (PDF, Excel, Word)."""

    def __init__(self, file_path: str) -> None:
        super().__init__(
            message=f"Fichier introuvable: {file_path}",
            code="SOURCE_FILE_NOT_FOUND",
            details={"file_path": file_path},
            suggestion="Verifier le chemin. Utiliser un chemin absolu commencant par /.",
            parameter="file_path",
            retry=True,
        )


class PDFCorruptedError(PDFError):
    """Fichier PDF corrompu ou illisible."""

    def __init__(self, file_path: str, reason: str = "") -> None:
        super().__init__(
            message=f"Fichier PDF corrompu: {file_path}",
            code="PDF_CORRUPTED",
            details={"file_path": file_path, "reason": reason},
            suggestion="Verifier que le fichier est un PDF valide et non corrompu.",
            parameter="file_path",
            retry=False,
        )


class PDFTooLargeError(PDFError):
    """Fichier PDF depasse la taille maximale."""

    def __init__(self, file_path: str, size_mb: float, max_size_mb: int) -> None:
        super().__init__(
            message=f"PDF trop volumineux: {size_mb:.1f}MB (max: {max_size_mb}MB)",
            code="PDF_TOO_LARGE",
            details={
                "file_path": file_path,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb,
            },
            suggestion=f"Utiliser un PDF de moins de {max_size_mb}MB ou le decouper.",
            parameter="file_path",
            retry=False,
        )


class PDFTooManyPagesError(PDFError):
    """PDF avec trop de pages."""

    def __init__(self, file_path: str, page_count: int, max_pages: int) -> None:
        super().__init__(
            message=f"PDF avec trop de pages: {page_count} (max: {max_pages})",
            code="PDF_TOO_MANY_PAGES",
            details={
                "file_path": file_path,
                "page_count": page_count,
                "max_pages": max_pages,
            },
            suggestion=f"Utiliser un PDF de moins de {max_pages} pages ou le decouper.",
            parameter="file_path",
            retry=False,
        )


# === OCR Errors ===


class OCRError(MCPZileoError):
    """Erreur liee au service OCR."""

    def __init__(
        self,
        message: str,
        code: str = "OCR_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class OCRAPIError(OCRError):
    """Erreur API Mistral OCR."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(
            message=f"Erreur API Mistral OCR: {message}",
            code="OCR_API_ERROR",
            details={"status_code": status_code, "api_message": message},
            suggestion="Probleme avec le service OCR. Reessayer dans quelques secondes.",
            retry=True,
        )


class OCRRateLimitError(OCRError):
    """Rate limit atteint sur l'API OCR."""

    def __init__(self, retry_after: int | None = None) -> None:
        wait_msg = f" Attendre {retry_after}s." if retry_after else ""
        super().__init__(
            message="Rate limit API Mistral OCR atteint",
            code="OCR_RATE_LIMIT",
            details={"retry_after_seconds": retry_after},
            suggestion=f"Limite de requetes atteinte.{wait_msg} Reessayer plus tard.",
            retry=True,
        )


# === Embedding Errors ===


class EmbeddingError(MCPZileoError):
    """Erreur liee au service d'embeddings."""

    def __init__(
        self,
        message: str,
        code: str = "EMBEDDING_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class EmbeddingAPIError(EmbeddingError):
    """Erreur API embeddings."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(
            message=f"Erreur API embeddings: {message}",
            code="EMBEDDING_API_ERROR",
            details={"status_code": status_code, "api_message": message},
            suggestion="Probleme avec le service d'embeddings. Reessayer dans quelques secondes.",
            retry=True,
        )


# === Vector Store Errors ===


class VectorStoreError(MCPZileoError):
    """Erreur liee au vector store."""

    def __init__(
        self,
        message: str,
        code: str = "VECTOR_STORE_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class VectorStoreConnectionError(VectorStoreError):
    """Impossible de se connecter au vector store."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(
            message=f"Impossible de se connecter a Qdrant: {host}:{port}",
            code="VECTOR_STORE_CONNECTION_ERROR",
            details={"host": host, "port": port},
            suggestion="Service de base vectorielle indisponible. Reessayer plus tard.",
            retry=True,
        )


class CollectionNotFoundError(VectorStoreError):
    """Collection introuvable dans le vector store."""

    def __init__(self, collection_name: str) -> None:
        super().__init__(
            message=f"Collection introuvable: {collection_name}",
            code="COLLECTION_NOT_FOUND",
            details={"collection_name": collection_name},
        )


class DocumentNotFoundError(VectorStoreError):
    """Document introuvable dans le vector store."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document introuvable: {document_id}",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id},
            suggestion="Ce document n'existe pas. Indexer d'abord avec index_document.",
            parameter="document_id",
            retry=False,
        )


# === Excel Generation Errors ===


class ExcelGenerationError(MCPZileoError):
    """Erreur liee a la generation de fichiers Excel."""

    def __init__(
        self,
        message: str,
        code: str = "EXCEL_GENERATION_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class ExcelOutputTooLargeError(ExcelGenerationError):
    """Fichier Excel genere depasse la taille maximale."""

    def __init__(self, filename: str, size_mb: float, max_size_mb: int) -> None:
        super().__init__(
            message=f"Fichier Excel trop volumineux: {size_mb:.1f}MB (max: {max_size_mb}MB)",
            code="EXCEL_OUTPUT_TOO_LARGE",
            details={
                "filename": filename,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb,
            },
            suggestion=f"Reduire le nombre de lignes ou de feuilles. Max {max_size_mb}MB.",
            parameter="sheets",
            retry=True,
        )


class ExcelChartError(ExcelGenerationError):
    """Erreur lors de la creation d'un graphique."""

    def __init__(self, chart_title: str | None, reason: str) -> None:
        super().__init__(
            message=f"Erreur graphique '{chart_title or 'sans titre'}': {reason}",
            code="EXCEL_CHART_ERROR",
            details={"chart_title": chart_title, "reason": reason},
            suggestion="Verifier data_range et categories_range du graphique.",
            retry=True,
        )


class ExcelFormulaInjectionError(ExcelGenerationError):
    """Formule dangereuse detectee dans une valeur de cellule."""

    def __init__(self, value: str, pattern: str) -> None:
        preview = value[:50] + "..." if len(value) > 50 else value
        super().__init__(
            message=f"Formule dangereuse detectee: {preview}",
            code="EXCEL_FORMULA_INJECTION",
            details={"value": preview, "matched_pattern": pattern},
            suggestion="Utiliser des formules Excel standard (SUM, AVERAGE, IF, etc.).",
            parameter="cells",
            retry=True,
        )


class ExcelFileNotFoundError(ExcelGenerationError):
    """Fichier Excel introuvable dans OUTPUT_PATH."""

    def __init__(self, filename: str) -> None:
        super().__init__(
            message=f"Fichier Excel introuvable: {filename}",
            code="EXCEL_FILE_NOT_FOUND",
            details={"filename": filename},
            suggestion="Verifier le nom. Creer d'abord avec create_excel_document.",
            parameter="filename",
            retry=True,
        )


class ExcelSheetNotFoundError(ExcelGenerationError):
    """Feuille introuvable dans le classeur."""

    def __init__(self, sheet_name: str, available: list[str]) -> None:
        super().__init__(
            message=f"Feuille introuvable: {sheet_name}",
            code="EXCEL_SHEET_NOT_FOUND",
            details={"sheet_name": sheet_name, "available_sheets": available},
            suggestion=f"Feuilles disponibles: {', '.join(available)}",
            parameter="sheet",
            retry=True,
        )


# === Presentation Generation Errors ===


class PresentationGenerationError(MCPZileoError):
    """Erreur liee a la generation de fichiers PowerPoint."""

    def __init__(
        self,
        message: str,
        code: str = "PRESENTATION_GENERATION_ERROR",
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        super().__init__(message, code, details, suggestion, parameter, retry)


class PresentationOutputTooLargeError(PresentationGenerationError):
    """Fichier PowerPoint genere depasse la taille maximale."""

    def __init__(self, filename: str, size_mb: float, max_size_mb: int) -> None:
        super().__init__(
            message=f"Fichier PowerPoint trop volumineux: {size_mb:.1f}MB (max: {max_size_mb}MB)",
            code="PRESENTATION_OUTPUT_TOO_LARGE",
            details={
                "filename": filename,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb,
            },
            suggestion=f"Reduire le nombre de slides ou d'images. Max {max_size_mb}MB.",
            parameter="slides",
            retry=True,
        )


class PresentationChartError(PresentationGenerationError):
    """Erreur lors de la creation d'un graphique dans une presentation."""

    def __init__(self, chart_title: str | None, reason: str) -> None:
        super().__init__(
            message=f"Erreur graphique '{chart_title or 'sans titre'}': {reason}",
            code="PRESENTATION_CHART_ERROR",
            details={"chart_title": chart_title, "reason": reason},
            suggestion="Verifier les donnees du graphique (categories, values, chart_type).",
            retry=True,
        )


class PresentationImageNotFoundError(PresentationGenerationError):
    """Image introuvable dans le dossier des images PowerPoint."""

    def __init__(self, filename: str, available: list[str]) -> None:
        super().__init__(
            message=f"Image introuvable: {filename}",
            code="PRESENTATION_IMAGE_NOT_FOUND",
            details={"filename": filename, "available_images": available},
            suggestion=f"Images disponibles: {', '.join(available[:20]) if available else 'aucune'}",
            parameter="image",
            retry=True,
        )


class PresentationTemplateNotFoundError(PresentationGenerationError):
    """Template PowerPoint introuvable."""

    def __init__(self, template: str, available: list[str]) -> None:
        super().__init__(
            message=f"Template introuvable: {template}",
            code="PRESENTATION_TEMPLATE_NOT_FOUND",
            details={"template": template, "available_templates": available},
            suggestion=f"Templates disponibles: {', '.join(available) if available else 'aucun'}",
            parameter="template",
            retry=True,
        )


class PresentationFileNotFoundError(PresentationGenerationError):
    """Fichier PowerPoint introuvable dans OUTPUT_PATH."""

    def __init__(self, filename: str) -> None:
        super().__init__(
            message=f"Fichier PowerPoint introuvable: {filename}",
            code="PRESENTATION_FILE_NOT_FOUND",
            details={"filename": filename},
            suggestion="Verifier le nom. Creer d'abord avec create_presentation.",
            parameter="filename",
            retry=True,
        )


class PresentationSlideNotFoundError(PresentationGenerationError):
    """Slide introuvable dans la presentation."""

    def __init__(self, slide_index: int, total_slides: int) -> None:
        super().__init__(
            message=f"Slide {slide_index} introuvable (presentation a {total_slides} slides)",
            code="PRESENTATION_SLIDE_NOT_FOUND",
            details={"slide_index": slide_index, "total_slides": total_slides},
            suggestion=f"Index de slide valide: 0 a {total_slides - 1}.",
            parameter="slide_index",
            retry=True,
        )


# === Validation Errors ===


class ValidationError(MCPZileoError):
    """Erreur de validation des donnees."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        suggestion: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=error_details,
            suggestion=suggestion,
            parameter=field,
            retry=True,
        )


class EmptyQueryError(ValidationError):
    """Requete de recherche vide."""

    def __init__(self) -> None:
        super().__init__(
            message="La requete de recherche est vide",
            field="query",
            suggestion="Fournir une requete en langage naturel. Ex: 'comment configurer X?'",
        )


class NoResultsError(MCPZileoError):
    """Aucun resultat trouve pour la recherche."""

    def __init__(self, query: str) -> None:
        preview = query[:50] + "..." if len(query) > 50 else query
        super().__init__(
            message=f"Aucun resultat pour: {preview}",
            code="NO_RESULTS",
            details={"query": query},
            suggestion="Reformuler avec d'autres mots-cles, ou verifier que des documents sont indexes.",
            parameter="query",
            retry=True,
        )
