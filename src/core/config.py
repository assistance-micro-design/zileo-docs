# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Configuration de l'application via pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application Zileo Docs.

    Toutes les valeurs peuvent etre surchargees via variables d'environnement.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Application ===
    APP_NAME: str = "Zileo Docs"
    APP_VERSION: str = "0.4.0"
    DEBUG: bool = False

    # === Mistral API ===
    MISTRAL_API_KEY: str = Field(
        default="",
        description="Cle API Mistral (requise pour OCR et embeddings)",
    )
    MISTRAL_OCR_MODEL: str = "mistral-ocr-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"
    MISTRAL_TIMEOUT_S: int = Field(
        default=30,
        ge=1,
        le=600,
        description="Timeout en secondes pour les appels Mistral (embeddings et OCR)",
    )

    # === Qdrant ===
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "documents"
    QDRANT_API_KEY: str | None = None

    # === Processing ===
    CHUNK_SIZE: int = Field(
        default=512,
        ge=100,
        le=2000,
        description="Taille cible des chunks en tokens",
    )
    CHUNK_OVERLAP: int = Field(
        default=50,
        ge=0,
        le=200,
        description="Chevauchement entre chunks en tokens",
    )
    OCR_DPI: int = Field(
        default=300,
        ge=72,
        le=600,
        description="Resolution DPI pour conversion en images",
    )
    OCR_MAX_CONCURRENT: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Nombre max de requetes OCR concurrentes",
    )
    OCR_TABLE_FORMAT: str = Field(
        default="markdown",
        pattern="^(markdown|html)$",
        description="Format de sortie des tableaux",
    )

    # === Limits ===
    MAX_FILE_SIZE_MB: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Taille max d'un fichier en MB",
    )
    MAX_PAGES: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Nombre max de pages par document",
    )

    # === Paths ===
    DOCUMENTS_PATH: str = Field(
        default="/app/documents",
        description="Chemin vers le dossier contenant les documents disponibles (PDF, Excel, Word)",
    )
    # === Output ===
    OUTPUT_PATH: str = Field(
        default="/app/output",
        description="Chemin vers le dossier de sortie des fichiers generes",
    )
    MAX_OUTPUT_FILE_SIZE_MB: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Taille max d'un fichier genere en MB",
    )
    MAX_MCP_BODY_MB: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Taille max du body JSON-RPC sur /mcp (DoS protection)",
    )
    MAX_DECOMPRESSED_MB: int = Field(
        default=200,
        ge=10,
        le=2000,
        description="Taille max decompressee pour .xlsx/.docx (anti zip-bomb)",
    )

    # === Authentication ===
    API_KEY: str = Field(
        default="",
        description="Cle API pour authentification (vide = pas d'auth)",
    )

    # === Rate Limiting ===
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_INDEX: str = "10/minute"
    RATE_LIMIT_MCP: str = "30/minute"
    RATE_LIMIT_SEARCH: str = "30/minute"

    # === Logging ===
    LOG_LEVEL: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )
    LOG_FORMAT: str = "json"


# Instance singleton
settings = Settings()
