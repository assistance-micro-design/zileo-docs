# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Assistance Micro Design
"""Core module: configuration, logging, exceptions."""

from __future__ import annotations

from src.core.config import Settings, settings
from src.core.exceptions import (
    DocumentNotFoundError,
    EmbeddingAPIError,
    EmbeddingError,
    OCRAPIError,
    OCRError,
    OCRRateLimitError,
    PDFCorruptedError,
    PDFError,
    PDFTooLargeError,
    PDFTooManyPagesError,
    SourceFileNotFoundError,
    ValidationError,
    VectorStoreConnectionError,
    VectorStoreError,
    ZileoDocsError,
)
from src.core.logging import setup_logging


__all__ = [
    "DocumentNotFoundError",
    "EmbeddingAPIError",
    "EmbeddingError",
    "OCRAPIError",
    "OCRError",
    "OCRRateLimitError",
    "PDFCorruptedError",
    "PDFError",
    "PDFTooLargeError",
    "PDFTooManyPagesError",
    "Settings",
    "SourceFileNotFoundError",
    "ValidationError",
    "VectorStoreConnectionError",
    "VectorStoreError",
    "ZileoDocsError",
    "settings",
    "setup_logging",
]
