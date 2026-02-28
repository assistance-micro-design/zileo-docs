# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Exceptions personnalisees pour l'application."""

from __future__ import annotations

from typing import Any


class MCPZileoPDFError(Exception):
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


class PDFError(MCPZileoPDFError):
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


class OCRError(MCPZileoPDFError):
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


class EmbeddingError(MCPZileoPDFError):
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


class VectorStoreError(MCPZileoPDFError):
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


# === Validation Errors ===


class ValidationError(MCPZileoPDFError):
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


class NoResultsError(MCPZileoPDFError):
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
