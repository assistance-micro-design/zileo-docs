# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Core module: configuration, logging, exceptions."""

from __future__ import annotations

from src.core.config import Settings, settings
from src.core.exceptions import (
    CollectionNotFoundError,
    DocumentNotFoundError,
    EmbeddingAPIError,
    EmbeddingError,
    MCPZileoPDFError,
    OCRAPIError,
    OCRError,
    OCRRateLimitError,
    PDFCorruptedError,
    PDFError,
    PDFNotFoundError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    ValidationError,
    VectorStoreConnectionError,
    VectorStoreError,
)
from src.core.logging import get_logger, setup_logging


__all__ = [
    "CollectionNotFoundError",
    "DocumentNotFoundError",
    "EmbeddingAPIError",
    "EmbeddingError",
    "MCPZileoPDFError",
    "OCRAPIError",
    "OCRError",
    "OCRRateLimitError",
    "PDFCorruptedError",
    "PDFError",
    "PDFNotFoundError",
    "PDFTooLargeError",
    "PDFTooManyPagesError",
    "Settings",
    "ValidationError",
    "VectorStoreConnectionError",
    "VectorStoreError",
    "get_logger",
    "settings",
    "setup_logging",
]
