# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 Assistance Micro Design
"""Exceptions personnalisees pour l'application."""

from __future__ import annotations

from typing import Any, ClassVar


class ZileoDocsError(Exception):
    """Classe de base pour toutes les exceptions de l'application.

    Inclut un champ `suggestion` pour guider les LLM sur comment corriger l'erreur.
    Les sous-classes peuvent surcharger `default_code` pour eviter de dupliquer __init__.
    """

    default_code: ClassVar[str] = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        suggestion: str | None = None,
        parameter: str | None = None,
        retry: bool = False,
    ) -> None:
        """Initialise l'exception.

        Args:
            message: Message d'erreur lisible.
            code: Code d'erreur unique. Si None, utilise `default_code` de la classe.
            details: Details supplementaires optionnels.
            suggestion: Conseil pour le LLM sur comment corriger l'erreur.
            parameter: Nom du parametre concerne (pour les erreurs de validation).
            retry: True si le LLM peut reessayer avec des parametres corriges.
        """
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
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


class PDFError(ZileoDocsError):
    """Erreur liee au traitement PDF."""

    default_code: ClassVar[str] = "PDF_ERROR"


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


class OCRError(ZileoDocsError):
    """Erreur liee au service OCR."""

    default_code: ClassVar[str] = "OCR_ERROR"


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


class EmbeddingError(ZileoDocsError):
    """Erreur liee au service d'embeddings."""

    default_code: ClassVar[str] = "EMBEDDING_ERROR"


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


class VectorStoreError(ZileoDocsError):
    """Erreur liee au vector store."""

    default_code: ClassVar[str] = "VECTOR_STORE_ERROR"


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


class ExcelGenerationError(ZileoDocsError):
    """Erreur liee a la generation de fichiers Excel."""

    default_code: ClassVar[str] = "EXCEL_GENERATION_ERROR"


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


# === Word Generation Errors ===


class WordGenerationError(ZileoDocsError):
    """Erreur liee a la generation de fichiers Word."""

    default_code: ClassVar[str] = "WORD_GENERATION_ERROR"


# === Validation Errors ===


class ValidationError(ZileoDocsError):
    """Erreur de validation des donnees."""

    default_code: ClassVar[str] = "VALIDATION_ERROR"

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
